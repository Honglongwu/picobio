#!/usr/bin/env python
"""Python script to remove tags from SAM/BAM files.

This script is designed to be used as part of a Unix pipeline. It
takes as optional command line arguments a white list of tags to
preserve (or a black list). It reads SAM format data from stdin,
and writes SAM format data to stdout.

The only change made to the SAM reads is in the SEQ field of mapped
reads. Any bases matching the reference are replaced with equals
signs. This makes the files much easier to compress, which can be
demonstrated by comparing a gzipped version of the SAM files with
and without the equals, or their BAM equivalents.

Simple usage with SAM files, keeping only read-group tags:

$ ./sam_strip_tags.py RG < original.sam > only_RG.sam

Simple usage with BAM files with conversion to/from SAM via samtools:

$ samtools view -h original.bam | ./sam_strip_tags.py RG | samtools view -S -b - > only_RG.bam

If your SAM/BAM files lack @SQ headers, you may need to give
samtools the reference FASTA file as well.

To remove particular tags (a black list rather than a white list)
include the switch -v (for invert, like the grep option). For example,
to remove any original quality (OC) tags, use:

$ ./sam_strip_tags.py -v OQ < original.sam > no_OQ.sam

Likewise with BAM files via samtools,

$ samtools view -h original.bam | ./sam_strip_tags.py -v OQ | samtools view -S -b - > no_OQ.bam
"""

import sys

if "-v" in sys.argv[1:]:
    black_list = set(x.strip() for x in sys.argv[1:] if x!="-v")
    sys.stderr.write("Removing these tags: %s\n" % ", ".join(black_list))
    for line in sys.stdin:
        if line[0]!="@":
            #Should be a read
            qname, flag, rname, pos, mapq, cigar, rnext, pnext, tlen, seq, qual, tags = line.rstrip().split("\t", 11)
            tags = "\t".join(t for t in tags.split("\t") if t[:2] not in black_list)
            line = "\t".join([qname, flag, rname, pos, mapq, cigar, rnext, pnext, tlen, seq, qual, tags]) + "\n"
        sys.stdout.write(line)
else:
    white_list = set(x.strip() for x in sys.argv[1:])
    sys.stderr.write("Keeping only these tags: %s\n" % ", ".join(white_list))
    for line in sys.stdin:
        if line[0]!="@":
            #Should be a read
            qname, flag, rname, pos, mapq, cigar, rnext, pnext, tlen, seq, qual, tags = line.rstrip().split("\t", 11)
            tags = "\t".join(t for t in tags.split("\t") if t[:2] in white_list)
            line = "\t".join([qname, flag, rname, pos, mapq, cigar, rnext, pnext, tlen, seq, qual, tags]) + "\n"
        sys.stdout.write(line)
