""" function to translate DNA codons to single character amino acids
"""

from __future__ import division
from __future__ import print_function


class ConservationMethods(object):
    """ class for conservation score methods, extended by the Interval class
    """
    
    def add_conservation_scores(self, conservation_scores):
        """ figure out the coding position relative to the CDS start site
        
        Converts the conservation score positions to CDS positions, so we can
        pull out scores by CDS position.
        
        Args:
            conservation_scores: dict of conservation scores, indexed by
                chromosome position
        """
        
        cds_chrom_start = self.get_cds_start()
        cds_chrom_end = self.get_cds_end()
        cds_length = self.get_coding_distance(cds_chrom_start, cds_chrom_end)
        
        cons_start = min(conservation_scores)
        cons_end = max(conservation_scores)
        
        # sometimes the conservation data doesn't contain values for the CDS, 
        # since the gene lies at the end of the chrom, or in a difficult region
        if cds_chrom_end > cons_end or cons_end < cds_chrom_end:
            raise ValueError("no conservation data for CDS")
        
        self.conservation_scores = {}
        cds_pos = 0
        while cds_pos < (cds_length + 1):
            chrom_pos = self.get_position_on_chrom(cds_pos)
            self.conservation_scores[cds_pos] = conservation_scores[chrom_pos]
            cds_pos += 1
    
    def get_conservation_score(self, cds_position):
        """ returns the phyloP conservation score at a CDS site
        """
        
        return self.conservation_scores[cds_position]
