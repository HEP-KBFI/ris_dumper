#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Example:
#
# ./ris_from_inspirehep.py             \
#    --name "Ehataht, Karl"            \
#    --out publications.ris            \
#    --date 2021-01-25                 \
#    --exclude PublicationDocument.ris \
#    --include-proceedings             \
#    --verbose
#
# It'll compile a RIS file of articles and conference proceedings (--include-proceedings)
# published since 25th of January 2021 (--date 2021-01-25), excluding entries specified
# in another RIS file (that's been downloaded from eg ETIS) based on DOI of each entry
# (--exclude PublicationDocument.ris), and saves the results to publications.ris
# (--out publications.ris) while logging every API interaction on screen (--verbose).
#
# The script has two more options: `--keep-affiliation' for maintaining the affiliation with
# NICPB even if it's not there, and --query-size that tells how many results per API interaction
# one should receive (defaults to 25).
#
# More resources:
# - https://github.com/inspirehep/rest-api-doc
# - https://help.inspirehep.net/knowledge-base/inspire-paper-search/
# - https://inspire-schemas.readthedocs.io/en/latest/schemas/hep.html
#
# Author: K. Ehatäht
# Date: 27-12-2021

import urllib.parse
import requests
import time
import collections
import math
import argparse
import os.path
import sys
import logging
import json

AFFIL = 'NICPB, Tallinn'

ALIASES = {
  'Carvalho Antunes De Oliveira, Alexandra' : 'Oliveira, Alexandra',
  'Ehataht, Karl'                           : 'Ehatäht, Karl',
}

DOCTYPES = {
  'article'          : 'JOUR',
  'conference paper' : 'CONF',
}

NUM_SFX = {
  '1' : 'st',
  '2' : 'nd',
  '3' : 'rd',
}

class SmartFormatter(argparse.HelpFormatter):
  def _split_lines(self, text, width):
    if text.startswith('R|'):
      return text[2:].splitlines()
    return argparse.HelpFormatter._split_lines(self, text, width)

def order_str(num):
  num_str = str(num)
  for num_key in NUM_SFX:
    if num_str.endswith(num_key) and not num_str.endswith(f'1{num_key}'):
      return num_str + NUM_SFX[num_key]
  return f'{num_str}th'

def get_doctype(doctype):
  if doctype not in DOCTYPES:
    raise RuntimeError("Unexpected document type: %s" % doctype)
  return DOCTYPES[doctype]

def join_with_and(arr):
  assert(arr)
  nof_elems = len(arr)
  if nof_elems == 1:
    return arr[0]
  elif nof_elems == 2:
    return f'{arr[0]} and {arr[1]}'
  else:
    first_part = ', '.join(arr[:-1])
    return f'{first_part} and {arr[-1]}'

def select(authors, name, keep_affiliation):
  selected_authors = []
  for author_item in authors:
    if 'affiliations' not in author_item:
      continue
    if any(affiliation['value'] == AFFIL for affiliation in author_item['affiliations']):
      selected_authors.append(author_item['full_name'])
  if name not in selected_authors:
    if name in ALIASES and ALIASES[name] in selected_authors:
      # we actually made it
      pass
    else:
      if keep_affiliation:
        selected_authors.append(author)
      else:
        # ignore the publication
        selected_authors = []
  selected_authors_aliased = sorted([
    ALIASES[author_name] if author_name in ALIASES else author_name for author_name in selected_authors
  ])
  return selected_authors_aliased

def get_ris(json_entry, name, keep_affiliation, dois_to_exclude):
  json_metadata = json_entry['metadata']

  record_url = f"https://inspirehep.net/record/{json_entry['id']}"
  if 'dois' not in json_metadata:
    logging.debug(f'Found a record that has no DOI: {record_url}')
    return []

  doi = json_metadata['dois'][0]['value']
  if doi in dois_to_exclude:
    logging.debug(f'Excluding DOI: {doi}')
    return []

  pub_idx = -1
  for idx, pubinfo in enumerate(json_metadata['publication_info']):
    if 'year' in pubinfo:
      pub_idx = idx
      break
  if pub_idx < 0:
    print(json.dumps(json_metadata, indent = 2))
    raise RuntimeError("No publication year found in the above entry")
  pubinfo = json_metadata['publication_info'][pub_idx]
  ris = collections.OrderedDict([
    ('ty', get_doctype(json_metadata['document_type'][0])),
    ('py', pubinfo['year']),
    ('jo', pubinfo['journal_title']),
    ('vl', pubinfo['journal_volume']),
    ('t1', json_metadata['titles'][0]['title']),
    ('do', f"https://dx.doi.org/{doi}"),
    ('db', 'WoS'),
    ('dp', 'WoS'),
    ('la', 'English'),
    ('ur', record_url),
  ])
  if 'page_start' in pubinfo:
    ris['sp'] = pubinfo['page_start']
  if 'page_end' in pubinfo:
    ris['ep'] = pubinfo['page_end']
  if 'documents' in json_metadata and 'url' in json_metadata['documents'][0]:
    ris['av'] = json_metadata['documents'][0]['url']
  elif 'urls' in json_metadata and 'value' in json_metadata['urls'][0]:
    ris['av'] = json_metadata['urls'][0]['value']

  authors_all = json_metadata['authors']
  nof_authors_total = len(authors_all)
  selected_authors = select(authors_all, name, keep_affiliation)
  if not selected_authors:
    return []

  if 'collaborations' in json_metadata:
    collabs = sorted([ collab['value'] for collab in json_metadata['collaborations'] ])
    collab_str = f'{join_with_and(collabs)} Collaboration'
    if len(collabs) > 1:
      collab_str += 's'
    if nof_authors_total < 10:
      selected_authors[-1] += f' (for the {collab_str})'
    else:
      selected_authors.append(f'et al. ({collab_str})')
  ris['au'] = selected_authors

  ris_lines = []
  for ris_key, ris_val in ris.items():
    ris_key_upper = ris_key.upper()
    if type(ris_val) == list:
      for ris_elem in ris_val:
        ris_lines.append(f'{ris_key_upper}  - {ris_elem}')
    else:
      ris_lines.append(f'{ris_key_upper}  - {ris_val}')
  return ris_lines

def exclude_dois_from(fn):
  to_exclude = []
  if fn:
    logging.debug(f'Excluding DOIs recorded in {fn}')
    if not os.path.isfile(fn):
      raise RuntimeError("No such file: %s" % fn)
    with open(fn, 'r', encoding = 'utf-16') as fptr:
      for line in fptr:
        line_stripped = line.strip()
        if line_stripped.startswith('DO '):
          line_split = line_stripped.split(' - ')
          if len(line_split) != 2:
            raise RuntimeError("Not a RIS file: %s" % fn)
          doi = line_split[1].strip().replace('https', 'http').replace('http://dx.doi.org/', '')
          to_exclude.append(doi)
    logging.debug(f'Found {len(to_exclude)} DOI(s) that we can exclude')
  return to_exclude


if __name__ == '__main__':
  parser = argparse.ArgumentParser(formatter_class = lambda prog: SmartFormatter(prog, max_help_position = 35))
  parser.add_argument('-n', '--name', dest = 'name', metavar = 'name', required = True, type = str,
                      help = "R|Author's name")
  parser.add_argument('-o', '--out', dest = 'output', metavar = 'file', required = False, type = str, default = '',
                      help = 'R|Output file (if none, print on screen)')
  parser.add_argument('-e', '--exclude', dest = 'exclude', metavar = 'file', required = False, type = str, default = '',
                      help = 'R|RIS file for exclusion')
  parser.add_argument('-d', '--date', dest = 'date', metavar = 'date', required = False, type = str, default = '',
                      help = 'R|Earliest date of publication (acceptable forms: yyyy, yyyy-mm and yyyy-mm-dd)')
  parser.add_argument('-s', '--query-size', dest = 'query_size', metavar = 'number', required = False, type = int,
                      default = 25,
                      help = 'R|Number of publications fetched per query')
  parser.add_argument('-k', '--keep-affiliation', dest = 'keep_affiliation', action = 'store_true', default = False,
                      help = f'R|Keep affiliation to: {AFFIL}')
  parser.add_argument('-p', '--include-proceedings', dest = 'include_proceedings', action = 'store_true', default = False,
                      help = 'R|Include conference proceedings')
  parser.add_argument('-v', '--verbose', dest = 'verbose', action = 'store_true', default = False,
                      help = 'R|Enable verbose printout')
  args = parser.parse_args()

  name = args.name
  date = args.date
  incl_conf_proc = args.include_proceedings
  query_size = args.query_size
  keep_affiliation = args.keep_affiliation
  output = args.output
  if output:
    output = os.path.abspath(output)
    output_dir = os.path.dirname(output)
    if not os.path.isdir(output_dir):
      raise RuntimeError("No directory for output file: %s" % output)

  logging.basicConfig(
    stream = sys.stdout,
    level  = logging.DEBUG if args.verbose else logging.INFO,
    format = '%(asctime)s - %(levelname)s: %(message)s'
  )
  dois_to_exclude = exclude_dois_from(args.exclude)

  doctypes = [ 'p' ]
  if incl_conf_proc:
    doctypes.append('c')
  doctype_query = ' or '.join([ f'tc {doctype}' for doctype in doctypes ])
  if len(doctypes) > 1:
    doctype_query = f'({doctype_query})'

  selection = [ f'a {name}', f'{doctype_query}' ]
  if date:
    selection.append(f'de > {date}')

  query = ' and '.join(selection)
  logging.debug(f"Constructed query: '{query}'")

  url_kv = {
    'q'      : query,
    'size'   : query_size,
    'page'   : 1,
    'format' : 'json',
    'sort'   : 'mostrecent',
  }

  url = f'https://inspirehep.net/api/literature?{urllib.parse.urlencode(url_kv)}'
  nof_hits = -1
  nof_pages = -1
  page_nr = 1

  ris_data = []
  while url:
    logging.debug(f'Trying URL: {url}')
    response = requests.get(url)
    if response.status_code == 429:
      # we need a timeout
      time.sleep(6)
      continue
    elif response.status_code != 200:
      raise RuntimeError("The following URL gave status code %d: %s" % (response.status_code, url))

    json_payload = response.json()
    json_hits = json_payload['hits']
    if nof_hits < 0:
      nof_hits = json_hits['total']
      nof_pages = int(math.ceil(nof_hits / query_size))
      logging.debug(f'Found {nof_hits} hit(s)')

    json_hits_data = json_hits['hits']
    logging.debug(f'Fetched {len(json_hits_data)} item(s) on {order_str(page_nr)} page out of {nof_pages}')
    page_nr += 1

    for json_entry in json_hits_data:
      ris_lines = get_ris(json_entry, name, keep_affiliation, dois_to_exclude)
      if ris_lines:
        ris_data.append('\n'.join(ris_lines))

    json_links = json_payload['links']
    url = json_links['next'] if 'next' in json_links else ''

  logging.debug(f'Found {len(ris_data)} entries')
  if output:
    with open(output, 'w') as output_f:
      output_f.write('\n\n'.join(ris_data))
    logging.debug(f'Saved results to {output}')
  else:
    print('\n\n'.join(ris_data))
