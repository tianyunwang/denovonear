""" Script to investigate the probability of multiple mutations clustering 
within a single gene.

simulate multiple mutations within a single gene using mutation rates
    only consider nonsynonymous mutations
    check functional type

simulate clustering of mutations
    sum the probabilities at each variant in the CDS for nonsynonymous mutations
    sum all the probabilities across all the positions in the CDS
    the likelihood of a specific mutation at a particular location is the 
    ratio of that specific trinucleotide change to the summed gene probability

cluster by distance:
    determine distance between two mutations (distance defined as within 
        coding sequence for longest CDS (if > one transcript))

    Rationale is:
        de novos closer together are increasingly unlikely
        multiple de novos hitting same position is near impossible
        three or more de novos - use mean distance between variants

compare clustering of simulated mutations to known mutations
    eg only 1% of the time we obtain de novos within 10 bp of each other

"""


from __future__ import print_function
from __future__ import division
import sys
import os
# import bisect
# import itertools
import time

from interval import Interval
from get_transcript_sequences import GetTranscriptSequence
# from weighted_choice import WeightedChoice
from load_mutation_rates import load_trincleotide_mutation_rates
from site_specific_rates import SiteRates
from load_known_de_novos import load_known_de_novos
from analyse_de_novos import AnalyseDeNovos

# define some paths and config files
USER_FOLDER = "/nfs/users/nfs_j/jm33/"
APP_FOLDER = os.path.join(USER_FOLDER, "apps", "mutation_rates")
DATA_FOLDER = os.path.join(APP_FOLDER, "data")

# ENSEMBL_TO_HGNC_FILE = os.path.join(DATA_FOLDER, "ensembl_transcript_id_to_hgnc_id.txt")
DEPRECATED_GENE_ID_FILE = os.path.join(DATA_FOLDER, "deprecated_ddg2p_hgnc_ids.txt")
MUTATION_RATES_FILE = os.path.join(DATA_FOLDER, "forSanger_1KG_mutation_rate_table.txt")
KNOWN_MUTATIONS_FILE = os.path.join(DATA_FOLDER, "DNG_Variants_28Jan2014.xlsx")
OUTPUT_FILE = os.path.join(DATA_FOLDER, "de_novo_distance_simulations.tsv")


def get_deprecated_gene_ids(filename):
    """ gets a dict of the gene IDs used during in DDD datasets that have been 
    deprecated in favour of other gene IDs
    """
    
    deprecated = {}
    with open(filename) as f:
        for line in f:
            line = line.strip().split()
            old = line[0]
            new = line[1]
            deprecated[old] = new
    
    return deprecated

def identify_transcript(ensembl, transcript_ids):
    """ for a given HGNC ID, finds the transcript with the longest CDS
    
    Args:
        ensembl: GetTranscriptSequence object to request sequences and data 
            from the ensembl REST API
        transcript_ids: list of transcript IDs for a single gene
    
    Returns:
        the transcript ID of the longest protein coding transcript in the list
    """
    
    max_length = 0
    max_transcript_id = None
    
    for transcript_id in transcript_ids:
        # get the transcript's protein sequence via the ensembl REST API
        seq = ensembl.get_protein_seq_for_transcript(transcript_id)
        
        # ignore transcripts without protein sequence
        if seq == "Sequence unavailable":
            continue
        
        # only swap to using the transcript if it is the longest
        if len(seq) > max_length:
            max_length = len(seq)
            max_transcript_id = transcript_id
    
    return max_transcript_id

def load_gene(ensembl, gene_id):
    """ sort out all the necessary sequences and positions for a gene
    
    Args:
        ensembl: GetTranscriptSequence object to request data from ensembl
        gene_id: HGNC symbol for gene
        
    Returns:
        Interval object for gene, including genomic ranges and sequences
    """
    
    # potential_transcript_ids = hgnc_mapper[gene_id]
    ensembl_genes = ensembl.get_genes_for_hgnc_id(gene_id)
    transcript_ids = ensembl.get_transcript_ids_for_ensembl_gene_ids(ensembl_genes)
    transcript_id = identify_transcript(ensembl, transcript_ids)
    
    # TODO: allow for genes without any coding sequence.
    if transcript_id == None:
        raise ValueError(gene_id + " lacks coding transcripts")
    
    # get the sequence for the identified transcript
    (chrom, start, end, strand, genomic_sequence) = ensembl.get_genomic_seq_for_transcript(transcript_id, expand=10)
    cds_sequence = ensembl.get_cds_seq_for_transcript(transcript_id)
    
    # get the locations of the exons and cds from ensembl
    cds_ranges = ensembl.get_cds_ranges_for_transcript(transcript_id)
    exon_ranges = ensembl.get_exon_ranges_for_transcript(transcript_id)
    
    # start an interval object with the locations and sequence
    transcript = Interval(transcript_id, start, end, strand, chrom, exon_ranges, cds_ranges)
    transcript.add_cds_sequence(cds_sequence)
    transcript.add_genomic_sequence(genomic_sequence, offset=10)
    
    return transcript


def main():
    # load all the data
    ensembl = GetTranscriptSequence()
    mut_dict = load_trincleotide_mutation_rates(MUTATION_RATES_FILE)
    old_gene_ids = get_deprecated_gene_ids(DEPRECATED_GENE_ID_FILE)
    known_de_novos = load_known_de_novos(KNOWN_MUTATIONS_FILE)
    
    output = open(OUTPUT_FILE, "w")
    output.write("\t".join(["gene_id", "functional_events_n", "func_dist", \
        "functional_probability", "missense_events_n", "missense_dist", \
        "missense_probability", "nonsense_events_n", "nonsense_distance", \
        "nonsense_probability"]) + "\n")
    
    iterations = 1000000
    for gene_id in known_de_novos:
        
        func_events = known_de_novos[gene_id]["functional"]
        missense_events = known_de_novos[gene_id]["missense"]
        nonsense_events = known_de_novos[gene_id]["nonsense"]
        
        # don't analyse genes with only one de novo functional mutation
        if len(func_events) < 2:
            continue
        
        # fix HGNC IDs that have been discontinued in favour of other gene IDs
        if gene_id in old_gene_ids:
            gene_id = old_gene_ids[gene_id]
        
        transcript = load_gene(ensembl, gene_id)
        site_weights = SiteRates(transcript, mut_dict)
        
        probs = AnalyseDeNovos(transcript, site_weights, iterations)
        
        (func_dist, func_prob) = probs.analyse_functional(func_events)
        (miss_dist, miss_prob) = probs.analyse_missense(missense_events)
        (nons_dist, nons_prob) = probs.analyse_nonsense(nonsense_events)
        
        output.write("{0}\t{1}\t{2}\t{3}\t{4}\t{5}\t{6}\t{7}\t{8}\t{9}\n".\
            format(gene_id, len(func_events), func_dist, func_prob, \
            len(missense_events), miss_dist, miss_prob, \
            len(nonsense_events), nons_dist, nons_prob))
        
        # sys.exit()
    
if __name__ == '__main__':
    main()





