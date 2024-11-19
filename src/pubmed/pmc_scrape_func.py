import requests
def pmid2biocxml(pmid):
    base_url = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/{pmid}/unicode"
    if not isinstance(pmid, list): pmid = [pmid]
    res = []
    for pmid_ in pmid:
        request_url = base_url.format(pmid=pmid_)
        response = requests.get(request_url)
        res.append(response.text)
    return res



"""
Parsers for PubMed XML
Adapted from "https://github.com/titipata/pubmed_parser/blob/master/pubmed_parser/pubmed_oa_parser.py".
"""
import pdb
import json
import collections
try:
    from collections.abc import Iterable
except:
    from collections import Iterable
from six import string_types
import os
import requests
from lxml import etree
from itertools import chain
import shutil
import re
import urllib.request
from contextlib import closing
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from unidecode import unidecode
import pandas as pd
import tenacity



__all__ = [
    "pmid2pmcid",
    "pmcid2ftplink",
    "ftplink2local",
    "pmid2papers",
    "pmid2biocxml",
    "parse_bioc_xml",
    "list_xml_path",
    "parse_pubmed_xml",
    "parse_pubmed_paragraph",
    "parse_pubmed_references",
    "parse_pubmed_caption",
    "parse_pubmed_table",
]

BATCH_REQUEST_SIZE = 400
SUMMARY_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id="
PUBMED_EFETCH_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id="

def remove_namespace(tree):
    """
    Strip namespace from parsed XML
    """
    for node in tree.iter():
        try:
            has_namespace = node.tag.startswith("{")
        except AttributeError:
            continue  # node.tag is not a string (node is a comment or similar)
        if has_namespace:
            node.tag = node.tag.split("}", 1)[1]


def read_xml(path, nxml=False):
    """
    Parse tree from given XML path
    """
    try:
        tree = etree.parse(path)
        if ".nxml" in path or nxml:
            remove_namespace(tree)  # strip namespace when reading an XML file
    except:
        try:
            tree = etree.fromstring(path)
        except Exception:
            print(
                "Error: it was not able to read a path, a file-like object, or a string as an XML"
            )
            raise
    return tree


def stringify_children(node):
    """
    Filters and removes possible Nones in texts and tails
    ref: http://stackoverflow.com/questions/4624062/get-all-text-inside-a-tag-in-lxml
    """
    parts = (
        [node.text]
        + list(chain(*([c.text, c.tail] for c in node.getchildren())))
        + [node.tail]
    )
    return "".join(filter(None, parts))


def stringify_affiliation(node):
    """
    Filters and removes possible Nones in texts and tails
    ref: http://stackoverflow.com/questions/4624062/get-all-text-inside-a-tag-in-lxml
    """
    parts = (
        [node.text]
        + list(
            chain(
                *(
                    [c.text if (c.tag != "label" and c.tag != "sup") else "", c.tail]
                    for c in node.getchildren()
                )
            )
        )
        + [node.tail]
    )
    return " ".join(filter(None, parts))

def _recur_children(node):
    """
    Recursive through node to when it has multiple children
    """
    if len(node.getchildren()) == 0:
        parts = (
            ([node.text or ""] + [node.tail or ""])
            if (node.tag != "label" and node.tag != "sup")
            else ([node.tail or ""])
        )
        return parts
    else:
        parts = (
            [node.text or ""]
            + [_recur_children(c) for c in node.getchildren()]
            + [node.tail or ""]
        )
        return parts

def _flatten(l):
    """
    Flatten list into one dimensional
    """
    for el in l:
        if isinstance(el, Iterable) and not isinstance(el, string_types):
            for sub in _flatten(el):
                yield sub
        else:
            yield el

def stringify_affiliation_rec(node):
    """
    Flatten and join list to string
    ref: http://stackoverflow.com/questions/2158395/flatten-an-irregular-list-of-lists-in-python
    """
    parts = _recur_children(node)
    parts_flatten = list(_flatten(parts))
    return " ".join(parts_flatten).strip()


"Start of the other APIs"
# utilities to automate the acquisition
def pmid2pmcid(pmid):
    base_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={ids}"
    if not isinstance(pmid, list): pmid = [pmid]
    pmid_str = ",".join(pmid)
    request_url = base_url.format(ids=pmid_str)
    response = requests.get(request_url)
    soup = BeautifulSoup(response.text, "html.parser")
    found = soup.find_all("record")
    res = []
    for rec in found:
        res.append(rec.get("pmcid", None))
    return res
    
def pmcid2ftplink(pmcid):
    base_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={pmcid}"
    if not isinstance(pmcid, list): pmcid = [pmcid]
    res = []
    for pmcid_ in pmcid:
        request_url = base_url.format(pmcid=pmcid_)
        response = requests.get(request_url)
        soup = BeautifulSoup(response.text, "html.parser")
        pdf_links = soup.find_all("link", attrs={"format": "tgz"})
        pdf_href_list = [link.get("href") for link in pdf_links]
        if len(pdf_href_list) > 0:
            pdf_href = pdf_href_list[0]
        else:
            pdf_href = None
        res.append(pdf_href)
    return res

def pmid2biocxml(pmid):
    base_url = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/{pmid}/unicode"
    if not isinstance(pmid, list): pmid = [pmid]
    res = []
    for pmid_ in pmid:
        request_url = base_url.format(pmid=pmid_)
        response = requests.get(request_url)
        res.append(response.text)
    return res
    
def ftplink2local(ftplink, output_dir):
    if not isinstance(ftplink, list):
        ftplink = [ftplink]
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    result_indicators = []
    for link in ftplink:
        match = re.search(r'/PMC(\d+)\.', link)
        if match:
            tgt_pmcid = match.group(1)  # Return the numeric part of the PMC ID
        else:
            tgt_pmcid = None
            result_indicators.append(None)
            continue

        output_path = os.path.join(output_dir, "PMC{}.tar.gz".format(tgt_pmcid))
            
        with closing(urllib.request.urlopen(link)) as r:
            with open(output_path, 'wb') as f:
                shutil.copyfileobj(r, f)
                
        # unzip the file under the folder
        import tarfile
        extract_path = os.path.dirname(output_path)
        with tarfile.open(output_path, "r:gz") as tar:
            tar.extractall(path=extract_path)
            
        result_indicators.append(output_path) # indicate the output path if the download succeeds
    return result_indicators

"Start of the functions from pubmed_parser/pubmed_oa_parser.py"

def list_xml_path(path_dir):
    """
    List full xml path under given directory

    Parameters
    ----------
    path_dir: str, path to directory that contains xml or nxml file

    Returns
    -------
    path_list: list, list of xml or nxml file from given path
    """
    fullpath = [
        os.path.join(dp, f)
        for dp, dn, fn in os.walk(os.path.expanduser(path_dir))
        for f in fn
    ]
    path_list = [
        folder
        for folder in fullpath
        if os.path.splitext(folder)[-1] in (".nxml", ".xml")
    ]
    return path_list


def zip_author(author):
    """
    Give a list of author and its affiliation keys
    in this following format
        [first_name, last_name, [key1, key2]]
    and return the output in
        [[first_name, last_name, key1], [first_name, last_name, key2]] instead
    """
    author_zipped = list(zip([[author[0], author[1]]] * len(author[-1]), author[-1]))
    return list(map(lambda x: x[0] + [x[-1]], author_zipped))


def flatten_zip_author(author_list):
    """
    Apply zip_author to author_list and flatten it
    """
    author_zipped_list = map(zip_author, author_list)
    return list(chain.from_iterable(author_zipped_list))


def parse_article_meta(tree):
    """
    Parse PMID, PMC and DOI from given article tree
    """
    article_meta = tree.find(".//article-meta")
    if article_meta is not None:
        pmid_node = article_meta.find('article-id[@pub-id-type="pmid"]')
        pmc_node = article_meta.find('article-id[@pub-id-type="pmc"]')
        pub_id_node = article_meta.find('article-id[@pub-id-type="publisher-id"]')
        doi_node = article_meta.find('article-id[@pub-id-type="doi"]')
    else:
        pmid_node = None
        pmc_node = None
        pub_id_node = None
        doi_node = None

    pmid = pmid_node.text if pmid_node is not None else ""
    pmc = pmc_node.text if pmc_node is not None else ""
    pub_id = pub_id_node.text if pub_id_node is not None else ""
    doi = doi_node.text if doi_node is not None else ""

    dict_article_meta = {"pmid": pmid, "pmc": pmc, "doi": doi, "publisher_id": pub_id}

    return dict_article_meta


def parse_coi_statements(tree):
    """
    Parse conflict of interest statements from given article tree
    """
    coi_paths = (
        'conflict',
        'CoiStatement',
        './/*[@*="conflict"]',
        './/*[@*="conflict-interest"]',
        './/*[@*="COI-statement"]',
    )

    for path in coi_paths:
        for el in tree.xpath(path):
            yield '\n'.join(el.itertext())


def parse_pubmed_xml(path, include_path=False, nxml=False):
    """
    Given an input XML path to PubMed XML file, extract information and metadata
    from a given XML file and return parsed XML file in dictionary format.
    You can check ``ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/`` to list of available files to download

    Parameters
    ----------
    path: str
        A path to a given PumMed XML file
    include_path: bool
        if True, include a key 'path_to_file' in an output dictionary
        default: False
    nxml: bool
        if True, this will strip a namespace of an XML after reading a file
        see https://stackoverflow.com/questions/18159221/remove-namespace-and-prefix-from-xml-in-python-using-lxml to
        default: False

    Return
    ------
    dict_out: dict
        A dictionary contains a following keys from a parsed XML path
        'full_title', 'abstract', 'journal', 'pmid', 'pmc', 'doi',
        'publisher_id', 'author_list', 'affiliation_list', 'publication_year',
        'publication_date', 'subjects'
    }
    """
    tree = read_xml(path, nxml)

    tree_title = tree.find(".//title-group/article-title")
    if tree_title is not None:
        title = [t for t in tree_title.itertext()]
        sub_title = tree.xpath(".//title-group/subtitle/text()")
        title.extend(sub_title)
        title = [t.replace("\n", " ").replace("\t", " ") for t in title]
        full_title = " ".join(title)
    else:
        full_title = ""

    try:
        abstracts = list()
        abstract_tree = tree.findall(".//abstract")
        for a in abstract_tree:
            for t in a.itertext():
                text = t.replace("\n", " ").replace("\t", " ").strip()
                abstracts.append(text)
        abstract = " ".join(abstracts)
    except BaseException:
        abstract = ""

    journal_node = tree.findall(".//journal-title")
    if journal_node is not None:
        journal = " ".join([j.text for j in journal_node])
    else:
        journal = ""

    dict_article_meta = parse_article_meta(tree)
    pub_year_node = tree.find(".//pub-date/year")
    pub_year = pub_year_node.text if pub_year_node is not None else ""
    pub_month_node = tree.find(".//pub-date/month")
    pub_month = pub_month_node.text if pub_month_node is not None else "01"
    pub_day_node = tree.find(".//pub-date/day")
    pub_day = pub_day_node.text if pub_day_node is not None else "01"

    subjects_node = tree.findall(".//article-categories//subj-group/subject")
    subjects = list()
    if subjects_node is not None:
        for s in subjects_node:
            subject = " ".join([s_.strip() for s_ in s.itertext()]).strip()
            subjects.append(subject)
        subjects = "; ".join(subjects)
    else:
        subjects = ""

    # create affiliation dictionary
    affil_id = tree.xpath(".//aff[@id]/@id")
    if len(affil_id) > 0:
        affil_id = list(map(str, affil_id))
    else:
        affil_id = [""]  # replace id with empty list

    affil_name = tree.xpath(".//aff[@id]")
    affil_name_list = list()
    for e in affil_name:
        name = stringify_affiliation_rec(e)
        name = name.strip().replace("\n", " ")
        affil_name_list.append(name)
    affiliation_list = [[idx, name] for idx, name in zip(affil_id, affil_name_list)]

    tree_author = tree.xpath('.//contrib-group/contrib[@contrib-type="author"]')
    author_list = list()
    for author in tree_author:
        author_aff = author.findall('xref[@ref-type="aff"]')
        try:
            ref_id_list = [str(a.attrib["rid"]) for a in author_aff]
        except BaseException:
            ref_id_list = ""
        try:
            author_list.append(
                [
                    author.find("name/surname").text,
                    author.find("name/given-names").text,
                    ref_id_list,
                ]
            )
        except BaseException:
            author_list.append(["", "", ref_id_list])
    author_list = flatten_zip_author(author_list)

    coi_statement = '\n'.join(parse_coi_statements(tree))

    dict_out = {
        "full_title": full_title.strip(),
        "abstract": abstract,
        "journal": journal,
        "pmid": dict_article_meta["pmid"],
        "pmc": dict_article_meta["pmc"],
        "doi": dict_article_meta["doi"],
        "publisher_id": dict_article_meta["publisher_id"],
        "author_list": author_list,
        "affiliation_list": affiliation_list,
        "publication_year": pub_year,
        "publication_date": "{}-{}-{}".format(pub_day, pub_month, pub_year),
        "subjects": subjects,
        "coi_statement": coi_statement,
    }
    if include_path:
        dict_out["path_to_file"] = path
    return dict_out


def parse_pubmed_references(path):
    """
    Given path to xml file, parse references articles
    to list of dictionary

    Parameters
    ----------
    path: str
        A string to an XML path.

    Return
    ------
    dict_refs: list
        A list contains dictionary for references made in a given file.
    """
    tree = read_xml(path)
    dict_article_meta = parse_article_meta(tree)
    pmid = dict_article_meta["pmid"]
    pmc = dict_article_meta["pmc"]

    references = tree.xpath(".//ref-list/ref[@id]")
    dict_refs = list()
    for reference in references:
        ref_id = reference.attrib["id"]

        if reference.find("mixed-citation") is not None:
            ref = reference.find("mixed-citation")
        elif reference.find("element-citation") is not None:
            ref = reference.find("element-citation")
        else:
            ref = None

        if ref is not None:
            if "publication-type" in ref.attrib.keys() and ref is not None:
                if ref.attrib.values() is not None:
                    journal_type = ref.attrib.values()[0]
                else:
                    journal_type = ""
                names = list()
                if ref.find("name") is not None:
                    for n in ref.findall("name"):
                        name = " ".join([t.text or "" for t in n.getchildren()][::-1])
                        names.append(name)
                elif ref.find("person-group") is not None:
                    for n in ref.find("person-group"):
                        name = " ".join(
                            n.xpath("given-names/text()") + n.xpath("surname/text()")
                        )
                        names.append(name)
                if ref.find("article-title") is not None:
                    article_title = stringify_children(ref.find("article-title")) or ""
                    article_title = article_title.replace("\n", " ").strip()
                else:

                    article_title = ""
                if ref.find("source") is not None:
                    journal = ref.find("source").text or ""
                else:
                    journal = ""
                if ref.find("year") is not None:
                    year = ref.find("year").text or ""
                else:
                    year = ""
                if len(ref.findall("pub-id")) >= 1:
                    for pubid in ref.findall("pub-id"):
                        if "doi" in pubid.attrib.values():
                            doi_cited = pubid.text
                        else:
                            doi_cited = ""
                        if "pmid" in pubid.attrib.values():
                            pmid_cited = pubid.text
                        else:
                            pmid_cited = ""
                else:
                    doi_cited = ""
                    pmid_cited = ""
                dict_ref = {
                    "pmid": pmid,
                    "pmc": pmc,
                    "ref_id": ref_id,
                    "pmid_cited": pmid_cited,
                    "doi_cited": doi_cited,
                    "article_title": article_title,
                    "name": "; ".join(names),
                    "year": year,
                    "journal": journal,
                    "journal_type": journal_type,
                }
                dict_refs.append(dict_ref)
    if len(dict_refs) == 0:
        dict_refs = None
    return dict_refs


def parse_pubmed_paragraph(path, all_paragraph=False):
    """
    Give path to a given PubMed OA file, parse and return
    a dictionary of all paragraphs, section that it belongs to,
    and a list of reference made in each paragraph as a list of PMIDs

    Parameters
    ----------
    path: str
        A string to an XML path.
    all_paragraph: bool
        By default, this function will only append a paragraph if there is at least
        one reference made in a paragraph (to aviod noisy parsed text).
        A boolean indicating if you want to include paragraph with no references made or not
        if True, include all paragraphs
        if False, include only paragraphs that have references
        default: False

    Return
    ------
    dict_pars: list
        A list contains dictionary for paragraph text and its metadata.
        Metadata includes 'pmc' of an article, 'pmid' of an article,
        'reference_ids' which is a list of reference ``rid`` made in a paragraph,
        'section' name of an article, and section 'text'
    """
    tree = read_xml(path)
    dict_article_meta = parse_article_meta(tree)
    pmid = dict_article_meta["pmid"]
    pmc = dict_article_meta["pmc"]

    paragraphs = tree.xpath("//body//p")
    dict_pars = list()
    for paragraph in paragraphs:
        paragraph_text = stringify_children(paragraph)
        section = paragraph.find("../title")
        if section is not None:
            section = stringify_children(section).strip()
        else:
            section = ""

        ref_ids = list()
        for reference in paragraph.getchildren():
            if "rid" in reference.attrib.keys():
                ref_id = reference.attrib["rid"]
                ref_ids.append(ref_id)

        dict_par = {
            "pmc": pmc,
            "pmid": pmid,
            "reference_ids": ref_ids,
            "section": section,
            "text": paragraph_text,
        }
        if len(ref_ids) >= 1 or all_paragraph:
            dict_pars.append(dict_par)

    return dict_pars


def parse_pubmed_caption(path):
    """
    Given single xml path, extract figure caption and
    reference id back to that figure

    Parameters
    ----------
    path: str
        A string to an PubMed OA XML path

    Return
    ------
    dict_captions: list
        A list contains all dictionary of figure ID ('fig_id') with its metadata.
        Metadata includes 'pmid', 'pmc', 'fig_caption' (figure's caption),
        'graphic_ref' (a file name corresponding to a figure file in OA bulk download)

    Examples
    --------
    >>> pubmed_parser.parse_pubmed_caption('data/pone.0000217.nxml')
    [{
        'pmid': '17299597',
        'pmc': '1790863',
        'fig_caption': "Fisher's geometric model in two-dimensional phenotypic space. ...",
        'fig_id': 'pone-0000217-g001',
        'fig_label': 'Figure 1',
        'graphic_ref': 'pone.0000217.g001'
    }, ...]
    """
    tree = read_xml(path)
    dict_article_meta = parse_article_meta(tree)
    pmid = dict_article_meta["pmid"]
    pmc = dict_article_meta["pmc"]

    figs = tree.findall(".//fig")
    dict_captions = list()
    if figs is not None:
        for fig in figs:
            fig_id = fig.attrib["id"]
            fig_label = stringify_children(fig.find("label"))
            fig_captions = fig.find("caption").getchildren()
            caption = " ".join([stringify_children(c) for c in fig_captions])
            graphic = fig.find("graphic")
            graphic_ref = None
            if graphic is not None:
                graphic_ref = graphic.attrib.values()[0]
            dict_caption = {
                "pmid": pmid,
                "pmc": pmc,
                "fig_caption": caption,
                "fig_id": fig_id,
                "fig_label": fig_label,
                "graphic_ref": graphic_ref,
            }
            dict_captions.append(dict_caption)
    if not dict_captions:
        dict_captions = None
    return dict_captions


def table_to_df(table_text):
    """
    This is a function to transform an input table XML text to list of row values and columns.
    This will return a list of column names, and list of list of values in the table

    Parameters
    ----------
    table_text: str
        An XML string of table parsed from PubMed OA

    Return
    ------
    columns, row_values: tuple (list, list)
        ``columns`` is a list of column names of the table,
        ``row_values`` is a list of list of values in the table
    """
    table_tree = etree.fromstring(table_text)
    columns = []
    for tr in table_tree.xpath("thead/tr"):
        for c in tr.getchildren():
            columns.append(unidecode(stringify_children(c)))

    row_values = []
    len_rows = []
    for tr in table_tree.findall("tbody/tr"):
        es = tr.xpath("td")
        row_value = [unidecode(stringify_children(e)) for e in es]
        len_rows.append(len(es))
        row_values.append(row_value)
    if len(len_rows) >= 1:
        len_row = max(set(len_rows), key=len_rows.count)
        row_values = [
            r for r in row_values if len(r) == len_row
        ]  # remove row with different length
        return columns, row_values
    else:
        return None, None


def parse_pubmed_table(path, return_xml=True):
    """
    Parse table from given Pubmed Open-Access XML file

    Parameters
    ----------
    path: str
        A string to an PubMed OA XML path
    return_xml: bool
        if True, a dictionary (in an output list)
        will have a key 'table_xml' which is an XML string of a parsed table
        default: True

    Return
    ------
    table_dicts: list
        A list contains all dictionary of table with its metadata.
        Metadata includes 'pmid', 'pmc', 'label' (in a full text), 'caption'
    """
    tree = read_xml(path)
    dict_article_meta = parse_article_meta(tree)
    pmid = dict_article_meta["pmid"]
    pmc = dict_article_meta["pmc"]

    # parse table
    # tables = tree.xpath(".//body.//sec.//table-wrap")
    # tables = tree.xpath("//body//sec//table-wrap")
    tables = tree.xpath("//table-wrap")
    table_dicts = list()
    for table in tables:
        if table.find("label") is not None:
            label = unidecode(table.find("label").text or "")
        else:
            label = ""

        # table caption
        if table.find("caption/p") is not None:
            caption_node = table.find("caption/p")
        elif table.find("caption/title") is not None:
            caption_node = table.find("caption/title")
        else:
            caption_node = None
        if caption_node is not None:
            caption = unidecode(stringify_children(caption_node).strip())
        else:
            caption = ""

        # table footnote
        if table.find("table-wrap-foot/fn") is not None:
            footnote_nodes = table.findall("table-wrap-foot/fn")
        elif table.find("table-wrap-foot/p") is not None:
            footnote_nodes = table.findall("table-wrap-foot/p")
        else:
            footnote_nodes = None
        
        if footnote_nodes is not None:
            footnotes = [unidecode(stringify_children(f).strip()) for f in footnote_nodes]
            footnote = "\n".join(footnotes)
        else:
            footnote = ""

        # table content
        if table.find("table") is not None:
            table_tree = table.find("table")
        elif table.find("alternatives/table") is not None:
            table_tree = table.find("alternatives/table")
        else:
            table_tree = None

        if table_tree is not None:
            table_xml = etree.tostring(table_tree)
            columns, row_values = table_to_df(table_xml)
            if row_values is not None:
                table_dict = {
                    "pmid": pmid,
                    "pmc": pmc,
                    "label": label,
                    "caption": caption,
                    "table_columns": columns,
                    "table_values": row_values,
                    "footnote": footnote,
                }
                if return_xml:
                    table_dict["table_xml"] = table_xml
                table_dicts.append(table_dict)
    if len(table_dicts) >= 1:
        return table_dicts
    else:
        return None
    

def parse_bioc_xml_title(bioc_text):
    # Check if path is a file path or XML string
    # Parse the XML
    soup = BeautifulSoup(bioc_text, features="xml")
    
    # Find the first text element in the entire document
    text_element = soup.find("text")
    
    if text_element:
        return text_element.text.strip()
    
    # If no title is found, return None
    return None

def parse_bioc_xml_authors(path):
    # Check if path is a file path or XML string
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as file:
            bioc_text = file.read()
    else:
        bioc_text = path
    
    # Parse the XML
    soup = BeautifulSoup(bioc_text, features="xml")
    
    # Find the first passage
    first_passage = soup.find("passage")
    
    if not first_passage:
        return []
    
    # Find all infon elements within the first passage
    infon_elements = first_passage.find_all("infon")
    authors = []
    for infon in infon_elements:
        key = infon.get("key", "")
        if key.startswith("name_"):
            author_info = infon.text.split(";")
            if len(author_info) == 2:
                surname = author_info[0].split(":")[1]
                given_names = author_info[1].split(":")[1]
                authors.append(f"{given_names} {surname}")
    
    return authors


def parse_bioc_xml_year(path):
    if os.path.exists(path):
        bioc_text = open(path, "r").read()
    else:
        bioc_text = path
    soup = BeautifulSoup(bioc_text, features="xml")
    passages = soup.find_all("passage")
    for passage in passages:
        infons = passage.find_all("infon")
        # print(infons)
        year = [info.text for info in infons if info.get("key") == "year"]
        # print(year)
        if year:
            return year[0]


def parse_bioc_xml_abstract(path):
    # Check if path is a file path or XML string
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as file:
            bioc_text = file.read()
    else:
        bioc_text = path
    
    # Parse the XML
    soup = BeautifulSoup(bioc_text, features="xml")
    
    # Debugging: Print the entire parsed XML structure
    # print("Parsed XML structure:")
    # print(soup.prettify())
    
    # Find all passages (now searching recursively)
    all_passages = soup.find_all("passage")
    print(f"Total number of passages found: {len(all_passages)}")
    
    # Filter passages with section_type ABSTRACT
    abstract_passages = [p for p in all_passages if p.find("infon", {"key": "section_type"}) and p.find("infon", {"key": "section_type"}).text == "ABSTRACT"]
    print(f"Number of ABSTRACT passages: {len(abstract_passages)}")
    
    abstract_parts = []
    for passage in abstract_passages:
        type_infon = passage.find("infon", {"key": "type"})
        text_element = passage.find("text")
        
        if type_infon and text_element:
            if type_infon.text == "abstract_title_1":
                abstract_parts.append(f"\n{text_element.text}\n")
            elif type_infon.text == "abstract":
                abstract_parts.append(text_element.text)
    
    return " ".join(abstract_parts).strip()


def parse_bioc_xml(path):
    """
    Parse BioC XML text to a list of dictionary of each passage
    and its metadata

    Parameters
    ----------
    path: str
        Path to the BioC formatted XML file.
        Or the input xml text.

    Return
    ------
    dict_bioc: list
        A list contains all dictionary of passage with its metadata.
        Metadata includes 'pmid', 'pmc', 'section' name of an article, and section 'text'
    """
    if os.path.exists(path):
        bioc_text = open(path, "r").read()
    else:
        bioc_text = path
    soup = BeautifulSoup(bioc_text, features="xml")
    passages = soup.find_all("passage")
    passage_dic = list()
    ref_dic = list()
    table_dic = list()
    fig_dic = list()
    author_contribution = list()
    comp_int = list()
    supplementary_material = list()

    for passage in passages:
        infons = passage.find_all("infon")
        section = [info.text for info in infons if info.get("key") == "section_type"]
        if len(section) == 0:
            section = ""
        else:
            section = section[0]

        pmid = [info.text for info in infons if info.get("key") == "article-id_pmid"]
        if len(pmid) == 0:
            pmid = ""
        else:
            pmid = pmid[0]

        pmcid = [info.text for info in infons if info.get("key") == "article-id_pmc"]
        if len(pmcid) == 0:
            pmcid = ""
        else:
            pmcid = pmcid[0]


        if section == "REF":
            texts = passage.find_all("text")
            texts = ". ".join([t.text for t in texts])
            ref_dic.append(
                {
                    "pmid": pmid,
                    "pmc": pmcid,
                    "section": section,
                    "content": texts,
                }
            )

        elif section == "TABLE":
            tab_ele_type = passage.find("infon", {"key": "type"})
            if tab_ele_type is not None: tab_ele_type = tab_ele_type.text
            tab_id = passage.find("infon", {"key": "id"})
            if tab_id is not None: tab_id = tab_id.text
            texts = passage.find_all("text")
            texts = ". ".join([t.text for t in texts])
            table_dic.append(
                {
                    "pmid": pmid,
                    "pmc": pmcid,
                    "section": section,
                    "tab_id": tab_id,
                    "tab_ele_type": tab_ele_type,
                    "content": texts,
                }
            )

        elif section == "FIG":
            fig_id = passage.find("infon", {"key": "id"})
            if fig_id is not None: fig_id = fig_id.text
            fig_caption = passage.find("infon", {"key": "caption"})
            if fig_caption is not None: fig_caption = fig_caption.text
            texts = passage.find_all("text")
            texts = ". ".join([t.text for t in texts])
            fig_dic.append(
                {
                    "pmid": pmid,
                    "pmc": pmcid,
                    "section": section,
                    "fig_id": fig_id,
                    "fig_caption": fig_caption,
                    "content": texts,
                }
            )

        elif section == "AUTH_CONT":
            texts = passage.find_all("text")
            texts = ". ".join([t.text for t in texts])
            author_contribution.append(
                {
                    "pmid": pmid,
                    "pmc": pmcid,
                    "section": section,
                    "content": texts,
                }
            )

        elif section == "COMP_INT":
            texts = passage.find_all("text")
            texts = ". ".join([t.text for t in texts])
            comp_int.append(
                {
                    "pmid": pmid,
                    "pmc": pmcid,
                    "section": section,
                    "content": texts,
                }
            )

        elif section == "SUPPL":
            texts = passage.find_all("text")
            texts = ". ".join([t.text for t in texts])
            supplementary_material.append(
                {
                    "pmid": pmid,
                    "pmc": pmcid,
                    "section": section,
                    "content": texts,
                }
            )

        else:
            texts = passage.find_all("text")
            texts = ". ".join([t.text for t in texts])
            passage_dic.append(
                {
                    "pmid": pmid,
                    "pmc": pmcid,
                    "section": section,
                    "content": texts,
                }
            )

    return {
        "passage": passage_dic,
        "ref": ref_dic,
        "table": table_dic,
        "figure": fig_dic,
        "author_contribution": author_contribution,
        "competing_interest": comp_int,
        "supplementary_material": supplementary_material,
    }

def pmid2papers(pmid_list: list[str], api_key: str = None):
    if len(pmid_list) == 0:
        return None, [], 0
    papers = _retrieve_abstract_from_efetch(pmid_list, api_key)
    return papers, "", len(pmid_list)

def _retrieve_abstract_from_efetch(pmids, api_key):
    """Retrieve the abstract from the efetch API."""
    all_abstracts = []
    for i in range(0, len(pmids), BATCH_REQUEST_SIZE):
        pmid_subset = pmids[i:i+BATCH_REQUEST_SIZE]
        pmid_str = ','.join(pmid_subset)
        query = PUBMED_EFETCH_BASE_URL + pmid_str + "&retmode=xml" + "&api_key=" + api_key
        logger.info(f"Abstract Query: {query}")
        response = get_response_with_retry(query)
        if response.status_code != 200:
            continue
        else:
            response = response.text
            tree = ET.fromstring(response)
            articles = tree.findall(".//PubmedArticle")
            for article in articles:
                try:
                    article_dict = _parse_article_xml_to_dict(article)
                    all_abstracts.append(article_dict)
                except:
                    continue

            # for books
            books = tree.findall(".//PubmedBookArticle")
            if len(books) > 0:
                for book in books:
                    try:
                        book_dict = _parse_book_xml_to_dict(book)
                        all_abstracts.append(book_dict)
                    except:
                        pass
    
    output_abstracts = pd.DataFrame.from_records(all_abstracts)
    return output_abstracts

def _parse_xml_recursively(element):
    child_dict = {}
    if element.text and element.text.strip():
        child_dict['text'] = element.text.strip()

    for child in element:
        if child.tag not in child_dict:
            child_dict[child.tag] = []
        child_dict[child.tag].append(_parse_xml_recursively(child))

    # Simplify structure when there's only one child or text
    for key in child_dict:
        if len(child_dict[key]) == 1:
            child_dict[key] = child_dict[key][0]
        elif not child_dict[key]:
            del child_dict[key]

    return child_dict

def _parse_article_xml_to_dict(article):
    results = {}
    dict_obj  = _parse_xml_recursively(article)

    # get article information
    article = dict_obj.get("MedlineCitation", {}).get("Article", {})

    # get the fields correspondingly
    results['PMID'] = dict_obj.get('MedlineCitation', {}).get('PMID', {}).get('text', '')

    # get the journal title
    journal = article.get('Journal', {}).get('Title', {}).get('text', '')
    results["Journal"] = journal

    # get pub date
    date = article.get('Journal', {}).get('JournalIssue', {})
    publication_year = date.get('PubDate', {}).get('Year', {}).get('text', '')
    publication_month = date.get('PubDate', {}).get('Month', {}).get('text', '')
    publication_day = date.get('PubDate', {}).get('Day', {}).get('text', '')
    results['Year'] = publication_year
    results['Month'] = publication_month
    results['Day'] = publication_day

    # get the title
    article_title = article.get('ArticleTitle', {}).get('text', '')
    results['Title'] = article_title

    # publication type
    publication_type = article.get('PublicationTypeList', {}).get('PublicationType', [])
    if len(publication_type) > 0:
        pubtype_list = []
        if isinstance(publication_type, dict):
            publication_type = [publication_type]
        for pt in publication_type:
            if isinstance(pt, dict):
                pubtype_list.append(pt.get('text', ''))
            else:
                pubtype_list.append(pt)
        publication_type = ", ".join(pubtype_list)
    else:
        publication_type = ""
    results['Publication Type'] = publication_type

    # authors
    author_names = article.get('AuthorList', {}).get('Author', [])
    authors = []
    if len(author_names) > 0:
        if isinstance(author_names, dict):
            author_names = [author_names]
        for author in author_names:
            last_name = author.get('LastName', {}).get('text', '')
            first_name = author.get('ForeName', {}).get('text', '')
            authors.append(f"{first_name} {last_name}")
        authors = ", ".join(authors)
    else:
        authors = ""
    results['Authors'] = authors

    # get the abstract
    abstracts = article.get('Abstract', {}).get('AbstractText', [])
    abstract_texts = []
    if len(abstracts) > 0:
        if isinstance(abstracts, dict):
            abstracts = [abstracts]
        for abstract in abstracts:
            if isinstance(abstract, dict):
                abstract_text = abstract.get('text', "")
            else:
                abstract_text = abstract
            abstract_texts.append(abstract_text)
        abstract_texts = "\n".join(abstract_texts)
    else:
        abstract_texts = ""
    results['Abstract'] = abstract_texts
    return results


def _parse_book_xml_to_dict(book):
    results = {}
    dict_obj  = _parse_xml_recursively(book)
    book = dict_obj.get("BookDocument")

    # get book information
    pmid = book.get("PMID", {}).get("text", "")
    results['PMID'] = pmid

    # get the book title
    book_title = book.get("Book", {}).get("BookTitle", {}).get("text", "")
    results['Title'] = book_title

    # pub date
    date = book.get("Book", {}).get('PubDate', {})
    publication_year = date.get('Year', {}).get('text', '')
    publication_month = date.get('Month', {}).get('text', '')
    publication_day = date.get('Day', {}).get('text', '')
    results['Year'] = publication_year
    results['Month'] = publication_month
    results['Day'] = publication_day

    # authors
    author_names = book.get('AuthorList', {}).get('Author', [])
    authors = []
    if len(author_names) > 0:
        if isinstance(author_names, dict):
            author_names = [author_names]
        for author in author_names:
            last_name = author.get('LastName', {}).get('text', '')
            first_name = author.get('ForeName', {}).get('text', '')
            authors.append(f"{first_name} {last_name}")
        authors = ", ".join(authors)
    else:
        authors = ""
    results['Authors'] = authors

    # get the abstract
    abstracts = book.get('Abstract', {}).get('AbstractText', [])
    abstract_texts = []
    if len(abstracts) > 0:
        if isinstance(abstracts, dict):
            abstracts = [abstracts]
        for abstract in abstracts:
            if isinstance(abstract, dict):
                abstract_text = abstract.get('text', "")
            else:
                abstract_text = abstract
            abstract_texts.append(abstract_text)
        abstract_texts = "\n".join(abstract_texts)
    else:
        abstract_texts = ""

    # get pub type
    publication_type = book.get('PublicationType', {}).get('text', '')
    results['Publication Type'] = publication_type
    return results