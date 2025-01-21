## RIS dumper

This repo contains utilities to import publications from [Inspire HEP](https://inspirehep.net/) to [ETIS](https://www.etis.ee/).

1. Export the current ETIS database status to RIS:
  - Get the list of current publications in ETIS: log in to ETIS->Research->Publications->Search publications
  - Export to RIS: Open in RIS (bottom of page) -> All publications -> Download the `PublicationDocument.ris` file (should be a few MB)

2. Download the new publications from Inspire that are linked to a specific CMS author, excluding the existing publications
```
python ris_from_inspirehep.py -n "Kadastik, Mario" --verbose --date 2024-01-01 --out publications.ris --include-proceedings --exclude PublicationDocument.ris
```
It should print something like this
```
2025-01-21 11:33:27,567 - DEBUG: Constructed query: 'a Kadastik, Mario and (tc p or tc c) and de > 2024-01-01'
2025-01-21 11:33:27,567 - DEBUG: Trying URL: https://inspirehep.net/api/literature?q=a+Kadastik%2C+Mario+and+%28tc+p+or+tc+c%29+and+de+%3E+2024-01-01&size=25&page=1&format=json&sort=mostrecent
2025-01-21 11:33:27,570 - DEBUG: Starting new HTTPS connection (1): inspirehep.net:443
2025-01-21 11:33:34,614 - DEBUG: https://inspirehep.net:443 "GET /api/literature?q=a+Kadastik%2C+Mario+and+%28tc+p+or+tc+c%29+and+de+%3E+2024-01-01&size=25&page=1&format=json&sort=mostrecent HTTP/11" 200 48911916
2025-01-21 11:33:44,551 - DEBUG: Found 55 hit(s)
2025-01-21 11:33:44,551 - DEBUG: Fetched 25 item(s) on 1st page out of 3
...
2025-01-21 11:34:48,617 - DEBUG: Fetched 5 item(s) on 3rd page out of 3
2025-01-21 11:34:48,618 - DEBUG: Excluding DOI: 10.1140/epjc/s10052-024-13114-9
2025-01-21 11:34:48,618 - DEBUG: Excluding DOI: 10.1103/PhysRevD.109.112013
2025-01-21 11:34:48,619 - DEBUG: Excluding DOI: 10.1088/1361-6633/ad4e65
2025-01-21 11:34:48,619 - DEBUG: Excluding DOI: 10.1088/1361-6633/ad4b9b
2025-01-21 11:34:48,620 - DEBUG: Found 7 entries
2025-01-21 11:34:48,620 - DEBUG: Saved results to /Users/joosep/ris_dumper/publications.ris
```

3. Double check the new publications file `publications.ris` using a text editor. Check that all DOIs exist, check manually that the DOIs lead to the correct place.
4. Upload the new publications file to ETIS. Do not forget to associate the authors also in ETIS!
