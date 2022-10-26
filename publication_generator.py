import calendar
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
import json
import sys

import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.customization import convert_to_unicode


def clean_bibtex_authors(author_str):
    """Convert author names to `firstname(s) lastname` format."""
    authors = []
    for s in author_str:
        s = s.strip()
        if len(s) < 1:
            continue

        if "," in s:
            split_names = s.split(",", 1)
            last_name = split_names[0].strip()
            first_names = [i.strip() for i in split_names[1].split()]
        else:
            split_names = s.split()
            last_name = split_names.pop()
            first_names = [i.replace(".", ". ").strip() for i in split_names]

        if last_name in ["jnr", "jr", "junior"]:
            last_name = first_names.pop()

        for item in first_names:
            if item in ["ben", "van", "der", "de", "la", "le"]:
                last_name = first_names.pop() + " " + last_name

        authors.append(" ".join(first_names) + " " + last_name)

    return authors


def clean_bibtex_str(s):
    """Clean BibTeX string and escape TOML special characters"""
    s = s.replace("\\", "")
    s = s.replace('"', '\\"')
    s = s.replace("{", "").replace("}", "")
    s = s.replace("\t", " ").replace("\n", " ").replace("\r", "")
    return s


def clean_bibtex_tags(s, normalize=False):
    """Clean BibTeX keywords and convert to TOML tags"""

    tags = clean_bibtex_str(s).split(",")
    tags = [tag.strip() for tag in tags]

    if normalize:
        tags = [tag.lower().capitalize() for tag in tags]

    return tags
            
def import_bibtex(bibtex, featured=False, overwrite=False, normalize=False, dry_run=False):
    data = []
    # Load BibTeX file for parsing.
    with open(bibtex, "r", encoding="utf-8") as bibtex_file:
        parser = BibTexParser(common_strings=True)
        parser.customization = convert_to_unicode
        parser.ignore_nonstandard_types = False
        bib_database = bibtexparser.load(bibtex_file, parser=parser)
        
        for entry in bib_database.entries:
            data.append(parse_bibtex_entry(entry, featured=featured, overwrite=overwrite, normalize=normalize, dry_run=dry_run,))            
    return data

def parse_bibtex_entry(entry, featured=False, overwrite=False, normalize=False, dry_run=False,):
    date = datetime.utcnow()
    timestamp = date.isoformat("T") + "Z"  # RFC 3339 timestamp.
    page = {}
    page["title"] = clean_bibtex_str(entry["title"])
    
    
    db = BibDatabase()
    db.entries = [entry]
    page['bibtex'] = bibtexparser.dumps(db)
    
    if "subtitle" in entry:
        page["subtitle"] = clean_bibtex_str(entry["subtitle"])
    
    if "year" in entry:
        page["year"] = year
    
    authors = None
    if "author" in entry:
        authors = entry["author"]
    elif "editor" in entry:
        authors = entry["editor"]

    if authors:
        authors = clean_bibtex_authors([i.strip() for i in authors.replace("\n", " ").split(" and ")])
        page["authors"] = authors

    if "abstract" in entry:
        page["abstract"] = clean_bibtex_str(entry["abstract"])
    else:
        page["abstract"] = ""

    page["featured"] = featured

    # Publication name.
    if "booktitle" in entry:
        publication = clean_bibtex_str(entry["booktitle"])
    elif "journal" in entry:
        publication = clean_bibtex_str(entry["journal"])
    elif "publisher" in entry:
        publication = clean_bibtex_str(entry["publisher"])
    else:
        publication = ""
    page["publication"] = publication

    if "keywords" in entry:
        page["tags"] = clean_bibtex_tags(entry["keywords"], normalize)

    if "doi" in entry:
        page["doi"] = clean_bibtex_str(entry["doi"])

    links = []
    if all(f in entry for f in ["archiveprefix", "eprint"]) and entry["archiveprefix"].lower() == "arxiv":
        links += [{"name": "arXiv", "url": "https://arxiv.org/abs/" + clean_bibtex_str(entry["eprint"])}]

    if "url" in entry:
        sane_url = clean_bibtex_str(entry["url"])

        if sane_url[-4:].lower() == ".pdf":
            page["url_pdf"] = sane_url
        else:
            links += [{"name": "URL", "url": sane_url}]

    if links:
        page["links"] = links

    return page

def makeBtn(entry):
    """
    Crea i pulsanti sotto a ogni pubblicazione
    """
    buttons = []
    if "doi" in entry:
        buttons.append(f'<a href="https://doi.org/{entry["doi"]}" class="btn btn-sm btn-primary">DOI</a>')
    if "url_pdf" in entry:
        buttons.append(f'<a href="{entry["url_pdf"]}" class="btn btn-sm btn-primary">PDF</a>')
    if "bibtex" in entry:
        bibtex = entry["bibtex"].replace("'", "\\'")
        bibtex = bibtex.replace("\r", "")
        bibtex = bibtex.replace("\n", "\\n")
        buttons.append(f'<a href="javascript:showBibtext(\'{bibtex}\')" class="btn btn-sm btn-primary">Cite</a>')
    
    return '&nbsp;'.join(buttons)

def makePub(entry):
    """
    Crea l'html per una pubblicazione
    """
    formatted = []
    formatted.append('<div class="publication">')    
    if "title" in entry:
        formatted.append(f'<b>{entry["title"]}</b>. ')
    if "authors" in entry:
        formatted.append(f'{", ".join(entry["authors"])}.')
    if "publication" in entry:
        formatted.append(f'<i>{entry["publication"]}</i>.')
    
    formatted.append('<div class="button-group">')
    formatted.append(makeBtn(entry))
    formatted.append('</div>')
    formatted.append('</div>')
    return "\n".join(formatted)


def makeYear(year, publications):
    """
    Crea le pubblicazioni per ogni anno
    """
    formatted = []
    formatted.append('<div class="bg-secondary text-white">')
    formatted.append('<h4>')
    formatted.append(f'<a class="btn btn-secondary" data-bs-toggle="collapse" data-bs-target="#c{year}" role="button" aria-expanded="true" aria-controls="#c{year}"><i class="bi bi-caret-down-square"></i></a>')
    formatted.append(f'{year} <i>({len(publications)})</i>')
    formatted.append('</h4>')
    formatted.append('</div>')
    formatted.append(f'<div class="collapse show" id="c{year}">')
    for entry in publications:
        formatted.append(makePub(entry))
    formatted.append('</div>')
    return "\n".join(formatted)


def makePage(data):
    """
    dato un bibtex formatta tutte le pubblicazioni
    """
    formatted = []
    years = sorted(list(set(map(lambda x: x['year'], data))), reverse=True)
    for year in years:
        publications = [d for d in data if d['year'] == year]
        formatted.append(makeYear(year, publications))
    return "\n".join(formatted)
    

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise('Specificare un file bibtex da elaborare')
    else:
        if not Path(sys.argv[1]).exists():
            raise('Specificare un file bibtex valido da elaborare')
        else:
            data = import_bibtex(sys.argv[1])
            page = makePage(data)
            out = open("template/template.html", "rt")
            txt = out.read()
            out.close()
            out = open("publications.html", "wt", encoding="utf-8")
            out.write(txt.replace('<!-- DATA HERE -->', page))
            out.close()
            print("Done!")