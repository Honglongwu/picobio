#!/usr/bin/env python
"""Python script for assembly comparison.
"""

import os
import sys
import warnings
from optparse import OptionParser

from Bio import BiopythonExperimentalWarning
with warnings.catch_warnings():
    warnings.simplefilter("ignore", BiopythonExperimentalWarning)
    from Bio import SearchIO

from Bio import SeqIO
from Bio.SeqIO.FastaIO import SimpleFastaParser
from Bio.SeqFeature import SeqFeature, FeatureLocation
from Bio.Blast.Applications import NcbiblastnCommandline

from reportlab.lib import colors
from reportlab.lib.colors import red, grey, orange, green, brown, blue, lightblue, purple
from reportlab.lib.units import cm

from Bio.Graphics import GenomeDiagram
from Bio.Graphics.GenomeDiagram import CrossLink

SPACER = 10000
MIN_GAP_JAGGY = 1000 # Sigils

MIN_HIT = 5000
MIN_GAP = 20000


usage = """Basic usage: multi_comparison.py reference.fasta assembly1.fasta assembly2.fasta -o figure.pdf

If a GenBank file exists next to FASTA file but with the extension *.gbk,
that will be loaded to draw any annotated genes.

There should be a (nucleotide) BLAST database next to the reference FASTA
file, created with some thing like this such that the BLAST database files
are named reference.fasta.n* and the database is referenced simply as
reference.fasta when calling blastn:

$ makeblastdb -in reference.fasta -dbtype nucl

The assembly FASTA files are expected to already be preordered, and
will each be drawn on one track with the contigs end to end (with a
spacer).
"""

def stop_err(msg, error_level=1):
    """Print error message to stdout and quit with given error level."""
    sys.stderr.write("%s\n" % msg.rstrip())
    sys.exit(error_level)

parser = OptionParser(usage=usage)
parser.add_option("-o", "--output", dest="pdf_filename",
                  help="Write PDF diagram to FILE (default automatic)",
                  default=None,
                  metavar="FILE")
(options, args) = parser.parse_args()

if len(args) < 2:
    stop_err("Requires two or more arguments!\n\n" + usage)
reference_fasta = args[0]
assemblies_fasta = args[1:]
diagram_pdf = options.pdf_filename

if not diagram_pdf:
    stop_err("Requires output PDF file to be specified!\n\n" + usage)
if not os.path.isfile(reference_fasta):
    stop_err("Reference FASTA file not found: %r" % reference_fasta)

reference_genbank = os.path.splitext(reference_fasta)[0] + ".gbk"

for assembly_fasta in assemblies_fasta:
    if not os.path.isfile(assembly_fasta):
        stop_err("Assembly FASTA file not found: %r" % assembly_fasta)

    output_stem = "%s_vs_%s" % (os.path.splitext(assembly_fasta)[0],
                            os.path.splitext(os.path.basename(reference_fasta))[0])
    blast_file = output_stem + ".blast.tsv"

def do_blast(query_fasta, db_fasta, blast_file):
    assert os.path.isfile(query_fasta)
    assert os.path.isfile(db_fasta)
    assert os.path.isfile(db_fasta + ".nhr")
    assert os.path.isfile(db_fasta + ".nin")
    assert os.path.isfile(db_fasta + ".nsq")
    cmd = NcbiblastnCommandline(query=query_fasta, db=db_fasta,
                                out=blast_file, outfmt=6,
                                evalue=1e-5)
    print cmd
    stdout, stderr = cmd()
    return

#TODO - Multiple references (e.g. with plasmids)
if os.path.isfile(reference_genbank):
    record = SeqIO.read(reference_genbank, "genbank")
else:
    record = SeqIO.read(reference_fasta, "fasta")
max_len = len(record)

gd_diagram = GenomeDiagram.Diagram("Comparison")
gd_track_for_features = gd_diagram.new_track(1,
                                             name=record.name,
                                             greytrack=False, height=0.5,
                                             start=0, end=len(record))
gd_feature_set = gd_track_for_features.new_set()
#Add a dark grey background
gd_feature_set.add_feature(SeqFeature(FeatureLocation(0, len(record))),
                           sigil="BOX", color="grey", label=False),
for feature in record.features:
    if feature.type != "gene":
        continue
    gd_feature_set.add_feature(feature, sigil="BOX",
                               color="lightblue", label=True,
                               label_position="start",
                               label_size=6, label_angle=0)
gd_record_features = gd_track_for_features.new_set()


def reverse_complement_hsp_fragment(frag, query_length):
    rev = SearchIO.HSPFragment(hit_id=frag.hit_id, query_id=frag.query_id)
    rev.query_start = query_length - frag.query_end
    rev.query_end = query_length - frag.query_start
    rev.hit_start = frag.hit_start
    rev.hit_end = frag.hit_end
    if frag.hit_strand == -1:
        rev.hit_strand = +1
    elif frag.hit_strand == +1:
        rev.hit_strand = -1
    else:
        #O or None,
        rev.hit_strand = frag.hit_strand
    return rev

def reverse_complement_hsp(hsp, query_length):
    rev = SearchIO.HSP(fragments = [reverse_complement_hsp_fragment(frag, query_length) \
                                    for frag in hsp.fragments[::-1]])
    rev.ident_pct = hsp.ident_pct
    return rev

def filter_blast(blast_result, query_length):
    hsps = [hsp for hsp in blast_result.hsps if (hsp.query_end - hsp.query_start) >= MIN_HIT]
    hsps = sorted(hsps, key = lambda hsp: hsp.hit_start)
    plus = 0
    minus = 0
    flipped = False
    for hsp in hsps:
        if hsp.hit_strand == -1:
            minus += hsp.hit_end - hsp.hit_start
        else:
            plus += hsp.hit_end - hsp.hit_start
    if minus > plus:
        #Reverse the contig
        flipped = True
        hsps = [reverse_complement_hsp(hsp, query_length) for hsp in hsps]
        hsps = sorted(hsps, key = lambda hsp: hsp.hit_start)
    return make_offset(hsps, query_length), blast_result.id, hsps, flipped


def weighted_median(values_and_weights):
    """Median of values with integer weights."""
    x = []
    count = sum(w for v, w in values_and_weights)
    map(x.extend,([v]*w for v, w in values_and_weights))
    return (x[count/2]+x[(count-1)/2])/2.


def make_offset(blast_hsps, contig_len):
    if not blast_hsps:
        return 0
    offset = int(weighted_median([(hsp.hit_start - hsp.query_start,
                                  hsp.hit_end - hsp.hit_start)
                                  for hsp in blast_hsps]))
    return min(max(0, offset), max_len - contig_len)

def add_jaggies(contig_seq, offset, gd_contig_features):
    """Add JAGGY features for any run of NNNN in sequence."""
    i = 0
    j = 0
    NNN = "N" * MIN_GAP_JAGGY
    while i < len(contig_seq):
        i = contig_seq.find(NNN, i)
        if i == -1:
            return
        j = i
        while j < len(contig_seq) and contig_seq[j] == "N":
            j += 1
        #print("Adding jaggy")
        gd_contig_features.add_feature(SeqFeature(FeatureLocation(offset+i, offset+j)),
                                       sigil="JAGGY",
                                       color=colors.slategrey, border=colors.black)
        i = j + 1

for assembly_fasta in assemblies_fasta:
    if not os.path.isfile(assembly_fasta):
        stop_err("Assembly FASTA file not found: %r" % assembly_fasta)

    output_stem = "%s_vs_%s" % (os.path.splitext(assembly_fasta)[0],
                            os.path.splitext(os.path.basename(reference_fasta))[0])
    blast_file = output_stem + ".blast.tsv"

    if not os.path.isfile(blast_file):
        do_blast(assembly_fasta, reference_fasta, blast_file)

    with open(assembly_fasta) as h:
        track_len = sum(len(seq)+SPACER for title, seq in SimpleFastaParser(h)) - SPACER
    #TODO - Configurable offset to visually align tracks?
    max_len = max(max_len, track_len)

    blast_results = SearchIO.index(blast_file, "blast-tab")

    gd_track = gd_diagram.new_track(3,
                                    name=assembly_fasta,
                                    greytrack=False, height=0.5,
                                    start=0, end=track_len)
    gd_contig_features = gd_track.new_set()
    
    offset = 0
    blast_data = SearchIO.index(blast_file, "blast-tab")
    h = open(assembly_fasta)
    for title, seq in SimpleFastaParser(h):
        contig_id = title.split(None,1)[0]
        contig_len = len(seq)

        #Add feature for whole contig,
        loc = FeatureLocation(offset, offset + contig_len, strand=0)
        gd_contig_features.add_feature(SeqFeature(loc), color=colors.grey, border=colors.black,
                                   label=True, name=contig_id)
        add_jaggies(seq, offset, gd_contig_features)
        #print "%s (len %i) offset %i" % (contig_id, contig_len, offset)

        if contig_id not in blast_data:
            offset += SPACER + contig_len
            continue
        xxx_offset, contig_id, blast_hsps, flipped = filter_blast(blast_data[contig_id], contig_len)
        if not blast_hsps:
            offset += SPACER + contig_len
            continue

        #Add cross-links,
        for hsp in blast_hsps:
            if flipped:
                if hsp.hit_strand == -1:
                    flip = True
                    color = colors.darkgreen
                else:
                    flip = False
                    color = colors.purple
            else:
                if hsp.hit_strand == -1:
                    flip = True
                    color = colors.blue
                else:
                    flip = False
                    color = colors.firebrick
            border = colors.lightgrey
            #Fade the colour based on percentage identify, 100% identity = 50% transparent
            color = colors.Color(color.red, color.green, color.blue, alpha=(hsp.ident_pct/200.0))
            loc = FeatureLocation(offset + hsp.query_start, offset + hsp.query_end, strand=0)
            query = gd_contig_features.add_feature(SeqFeature(loc), color=color, border=border)
            loc = FeatureLocation(hsp.hit_start, hsp.hit_end, strand=0)
            hit = gd_record_features.add_feature(SeqFeature(loc), color=color, border=border)
            gd_diagram.cross_track_links.append(CrossLink(query, hit, color, border, flip))

        offset += SPACER + contig_len
    h.close()

#Set size based on max track length?
page = (30*cm, 100*cm*max_len/5000000)
gd_diagram.draw(format="linear", fragments=1,
                pagesize=page, start=0, end=max_len)
gd_diagram.write(diagram_pdf, "PDF")
print("Saved %r" % diagram_pdf)
