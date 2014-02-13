#!/usr/bin/env python
"""Python script to convert SAM/BAM to SSPACE tab format.

Converts a SAM/BAM file containing mapped paired-end data into the
simple tab separated format used by the assembly scaffolder SSPACE:

    <contig1> <startpos_on_contig1> <endpos_on_contig1> <contig2> <startpos_on_contig2> <endpos_on_contig2>

e.g.

    contig1 100 150 contig1 350 300
    contig1 4000 4050 contig2 110 60

Essentially this is a rewrite of tools/sam_bam2Tab.pl script included
in SSPACE basic v2.0 to actually handle real SAM/BAM files where the
paired end data is correctly encoded using the FLAG field rather than
read name suffices.

Simple usage with a paired-end SAM file:

$ ./sam_to_sspace_tab.py < original.sam > converted.tab

Simple usage with BAM files with conversion to/from SAM via samtools:

$ samtools view original.bam | ./sam_to_sspace_tab.py > converted.tab

TODO:

 * Actual mapped lengths (may need name sorted as in Perl original
   in order to efficiently get the partner read's mapped length)
 * Separate output file for each read group (as different pair
   lengths, should be a different line in the SSPACE input)
 * Report progress to stderr

Copyright Peter Cock 2014. All rights reserved. See:
https://github.com/peterjc/picobio
"""

import sys

def cigar_mapped_len(cigar):
    #TODO
    return 1

reads = 0
pairs = 0
interesting = 0
min_len = None
max_len = None
for line in sys.stdin:
    if line[0]=="@":
        #Header line
        contine
    #Should be a read
    reads += 1
    qname, flag, rname, pos, mapq, cigar, rnext, pnext, tlen, seq, qual, tags = line.rstrip().split("\t", 11)
    flag = int(flag)
    if (not (flag & 0x1) # Single end read
        or flag & 0x4 # Unmapped
        or flag & 0x8 # Partner unmapped
        or flag & 0x80 or not (flag & 0x40) #Only using read one (and the RNEXT/PNEXT information for read two)
        or flag & 0x100 or flag & 0x800 #Ignore secondary or supplementary alignments
        or flag & 0x200 # failed QC
        or flag & 0x400 # PCR or optical duplicate
        ):
        #Ignore this read
        continue
    len1 = cigar_mapped_len(cigar)
    len2 = len1 # TODO - this is a quick approximation...
    if flag & 0x16:
        # Read one is on the reverse strand
        end1 = int(pos)
        start1 = end1 - len1 + 1
    else:
        # Read one is on the forward strand
        start1 = int(pos)
        end1 = start1 + len1 - 1
    if flag & 0x20:
        # Partner (read two) is on the reverse strand
        end2 = int(pnext)
        start2 = end2 - len2 + 1
    else:
        # Partner (read two) is on the forward strand
        start2 = int(pnext)
        end2 = start2 + len2 - 1
    if rnext == "=":
        rnext = rname
    if rname == rnext:
        tlen = abs(int(tlen))
        if tlen:
            if min_len is None:
                min_len = max_len = tlen
            else:
                min_len = min(min_len, tlen)
                max_len = max(max_len, tlen)
    else:
        interesting += 1
    sys.stdout.write("%s\t%i\t%i\t%s\t%i\t%i\n" % (rname, start1, end1, rnext, start2, end2))
    pairs += 1
sys.stderr.write("Extracted %i pairs from %i reads\n" % (pairs, reads))
sys.stderr.write("Of these, %i pairs are mapped to different contigs\n" % interesting)
if interesting:
    sys.stderr.write("Size range when mapped to same contig %r to %r\n" % (min_len, max_len))
