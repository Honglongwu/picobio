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


usage = """Basic usage: multi_comparison.py assembly1.fasta assembly2.fasta assembly3.fasta -o figure.pdf

If a GenBank file exists next to FASTA file but with the extension *.gbk,
that will be loaded to draw any annotated genes. e.g. reference genome.

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
assemblies_fasta = args[:]
diagram_pdf = options.pdf_filename

if not diagram_pdf:
    stop_err("Requires output PDF file to be specified!\n\n" + usage)

for assembly_fasta in assemblies_fasta:
    if not os.path.isfile(assembly_fasta):
        stop_err("Assembly FASTA file not found: %r" % assembly_fasta)

def do_blast(query_fasta, db_fasta, blast_file):
    assert os.path.isfile(query_fasta)
    assert os.path.isfile(db_fasta)
    assert os.path.isfile(db_fasta + ".nhr"), "Missing database for %s" % db_fasta
    assert os.path.isfile(db_fasta + ".nin"), "Missing database for %s" % db_fasta
    assert os.path.isfile(db_fasta + ".nsq"), "Missing database for %s" % db_fasta
    cmd = NcbiblastnCommandline(query=query_fasta, db=db_fasta,
                                out=blast_file, outfmt=6,
                                evalue=1e-5)
    print cmd
    stdout, stderr = cmd()
    return


def filter_blast(blast_result, query_length):
    hsps = [hsp for hsp in blast_result.hsps if (hsp.query_end - hsp.query_start) >= MIN_HIT]
    hsps = sorted(hsps, key = lambda hsp: hsp.hit_start)
    return blast_result.id, hsps


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

max_len = 0
gd_diagram = GenomeDiagram.Diagram("Comparison")
reference_fasta = None
ref_offsets = dict()
for i, assembly_fasta in enumerate(assemblies_fasta):
    if not os.path.isfile(assembly_fasta):
        stop_err("Assembly FASTA file not found: %r" % assembly_fasta)
    assembly_genbank = os.path.splitext(assembly_fasta)[0] + ".gbk"

    contig_offsets = dict()
    track_len = -SPACER
    with open(assembly_fasta) as h:
        for title, seq in SimpleFastaParser(h):
            track_len += SPACER
            contig_offsets[title.split(None, 1)[0]] = track_len
            track_len += len(seq)
    #TODO - Configurable offset to visually align tracks?
    max_len = max(max_len, track_len)

    gd_track = gd_diagram.new_track(1 + 2 * i,
                                    name=assembly_fasta,
                                    greytrack=False, height=0.5,
                                    start=0, end=track_len)
    gd_contig_features = gd_track.new_set()


    if reference_fasta:
        output_stem = "%s_vs_%s" % (os.path.splitext(assembly_fasta)[0],
                                    os.path.splitext(os.path.basename(reference_fasta))[0])
        blast_file = output_stem + ".blast.tsv"

        if not os.path.isfile(blast_file):
            do_blast(assembly_fasta, reference_fasta, blast_file)
        blast_data = SearchIO.index(blast_file, "blast-tab")
    else:
        assert i == 0
        blast_data = dict()

    
    offset = 0
    if os.path.isfile(assembly_genbank):
        print("Using %s" % assembly_genbank)
        contigs = SeqIO.parse(assembly_genbank, "genbank")
    else:
        contigs = SeqIO.parse(assembly_fasta, "fasta")
    for contig in contigs:
        contig_id = contig.id
        contig_len = len(contig)

        #Add feature for whole contig,
        loc = FeatureLocation(offset, offset + contig_len, strand=0)
        gd_contig_features.add_feature(SeqFeature(loc), color=colors.grey, border=colors.black,
                                   label=True, name=contig_id)
        #Mark any NNNN regions,
        add_jaggies(str(contig.seq), offset, gd_contig_features)
        #Mark any genes (if using GenBank file),
        for feature in contig.features:
            if feature.type != "gene":
                continue
            feature.location += offset
            gd_contig_features.add_feature(feature, sigil="BOX",
                                           color="lightblue", label=True,
                                           label_position="start",
                                           label_size=6, label_angle=0)

        #print "%s (len %i) offset %i" % (contig_id, contig_len, offset)

        if contig_id not in blast_data:
            offset += SPACER + contig_len
            continue
        contig_id, blast_hsps = filter_blast(blast_data[contig_id], contig_len)
        if not blast_hsps:
            offset += SPACER + contig_len
            continue

        #Add cross-links,
        for hsp in blast_hsps:
            if hsp.hit_strand == -1:
                flip = True
                color = colors.blue
            else:
                flip = False
                color = colors.firebrick
            border = colors.lightgrey
            #Fade the colour based on percentage identify, 100% identity = 50% transparent
            color = colors.Color(color.red, color.green, color.blue, alpha=(hsp.ident_pct/200.0))
            assert offset == contig_offsets[hsp.query_id]
            loc = FeatureLocation(offset + hsp.query_start, offset + hsp.query_end, strand=0)
            query = gd_contig_features.add_feature(SeqFeature(loc), color=color, border=border)
            r_offset = ref_offsets[hsp.hit_id]
            loc = FeatureLocation(r_offset + hsp.hit_start, r_offset + hsp.hit_end, strand=0)
            hit = gd_ref_features.add_feature(SeqFeature(loc), color=color, border=border)
            gd_diagram.cross_track_links.append(CrossLink(query, hit, color, border, flip))

        offset += SPACER + contig_len

    #Ready for next pairwise comparison,
    reference_fasta = assembly_fasta
    ref_offsets = contig_offsets
    gd_ref_features = gd_contig_features

#Set size based on max track length?
page = (2*cm + 5*cm*len(assemblies_fasta), 100*cm*max_len/5000000)
gd_diagram.draw(format="linear", fragments=1,
                pagesize=page, start=0, end=max_len)
gd_diagram.write(diagram_pdf, "PDF")
print("Saved %r" % diagram_pdf)
