"""Created:  Friday July 20, 2018
   Modified: Thursday August 2, 2018
   Jorge Luis Flores
   Calculates the similarity between each mRNA and a sequence from a given file containing the calculated vectors of mRNA.
   Stores in .csv files a matrix where each row corresponds to an mRNA, and each column corresponds to  the Jaccard index of the 
   79-nucleotide window starting at that nucleotide position (where mRNA is zero-indexed, and each column skips 4 nucleotides).
   
   Similarity is measured by calculating p-values for each motif, assuming a Poisson distribution. These p-values are then used
   to determine whether each motif is 'important' or not, using a predefined a cut-off (p-val < 0.05 in this case). 
   Each 'important' motif is scored as '1', and then the similarity between each window and the signature of aptamer-21 is 
   calculated as a Jaccard index."""
import sys
sys.path.append('/u/floresj/Pyth_modules/')
import multiprocessing
import subprocess

from datetime import datetime as dt

from Bio.SeqIO import parse
import motifs_vector_3 as mv
import numpy as np
import pandas as pd
from scipy.stats import poisson

ALL_MOTIFS = mv.list_of_all_motifs()
WIN_SIZE = 79
NT_SKIP = 4

#FILE_NUMBER = '02'
if __name__ == '__main__':
    # specify file number to process
    #FILE_NUMBER = input('01, 02, 03, ... 13\nWhich file subset to process...')
    FILE_NUMBER = sys.argv[1]
    print( 'Script is processing subset: '+FILE_NUMBER )

def same_length(vec_1, vec_2):
    """Checks that both vectors are of the same length and thus comparable."""
    # signatures must be of same length, i.e. 940 entries
    if not len(vec_1) == len(vec_2):
        raise TypeError(f'The vector and the signature are not of the same length. Vector is {len(mrna_vector)} and signature is {len(target_sig)}')
    
def get_jaccard_index_pval(mrna_vector, target_sig):
    """Calculates the Jaccard index of mrna_vector with respect to target_sig ().
       The Jaccard index is defined as J(x, y) = sum(min(x_i, y_i)) / sum(max(x_i, y_i)).
       
       https://en.wikipedia.org/wiki/Jaccard_index"""
    
    # signatures must be of same length, i.e. 940 entries
    same_length( mrna_vector, target_sig )
    
    dividend = sum( [min(x, y) for x, y in zip(mrna_vector, target_sig)] )
    divisor  = sum( [max(x, y) for x, y in zip(mrna_vector, target_sig)] )
    
    return dividend / divisor

def get_simple_similarity(rna_vector, target_sig):
    same_length( rna_vector, target_sig )

    # signatures must both contain either 0 or 1
    for i in range(len(rna_vector)):
        if not ( (rna_vector[i] == 0) or (rna_vector[i] == 1) ): 
            raise ValueError('The vector contains values other than 0 or 1.')
        if not ( (target_sig[i] == 0) or (target_sig[i] == 1) ):
            raise ValueError('The signature contains values other than 0 or 1.')
    
    # check every binary attribute in both vectors
    M_11 = 0    # number of attributes where both M and T have value of 1
    M_01 = 0    # number of attributes where M is 0 and T is 1
    M_10 = 0    # number of attributes where M is 1 and T is 0
    
    for i in range(len(rna_vector)):
        if   ( rna_vector[i] == target_sig[i] == 1 ):
            M_11 += 1
        #elif ( rna_vector[i] == 0 ) and ( target_sig[i] == 1 ):
        #    M_01 += 1
        #elif ( rna_vector[i] == 1 ) and ( target_sig[i] == 0 ):
        #    M_10 += 1
    
    return M_11

def get_jaccard_index(mrna_vector, target_sig):
    """Calculates the Jaccard index of mrna_vector (M) with respect to target_sig (T) (binary values based on p-values).
       Each signature is treated as a set containing a binary value for a feature.
       The Jaccard index is thus defined as J(M, T) = | M n T | / | M u T |"""
    
    # signatures must be of same length, i.e. 940 entries
    same_length( mrna_vector, target_sig )
    
    # signatures must both contain either 0 or 1
    for i in range(len(mrna_vector)):
        if not ( (mrna_vector[i] == 0) or (mrna_vector[i] == 1) ): 
            raise ValueError('The vector contains values other than 0 or 1.')
        if not ( (target_sig[i] == 0) or (target_sig[i] == 1) ):
            raise ValueError('The signature contains values other than 0 or 1.')
    
    # check every binary attribute in both vectors
    M_11 = 0    # number of attributes where both M and T have value of 1
    M_01 = 0    # number of attributes where M is 0 and T is 1
    M_10 = 0    # number of attributes where M is 1 and T is 0
    
    for i in range(len(mrna_vector)):
        if   ( mrna_vector[i] == target_sig[i] == 1 ):
            M_11 += 1
        elif ( mrna_vector[i] == 0 ) and ( target_sig[i] == 1 ):
            M_01 += 1
        elif ( mrna_vector[i] == 1 ) and ( target_sig[i] == 0 ):
            M_10 += 1
    
    return ( M_11 / (M_01+M_10+M_11) )

def get_jaccard_distance(mrna_vector, target_sig):
    jacc_index = get_jaccard_index(mrna_vector, target_sig)

    return 1 - jacc_index

def get_binary_features(vector, pval=.05):
    """Takes as input a vector containing a collection of p-values and transforms it in a vector of binary values.
       In this vector, 0 means that p-value(feature) > cut-off,
       and             1 means that p-value(feature) < cut-off."""
    
    features = np.zeros(940, dtype=int)
    
    ## a p-value = 0, in the context of Mathieu's script for aptamer-21, means that it is extremely small
    
    # check every feature, score as 1 if the p-value is below threshold
    # otherwise feature remains at 0
    for i, feat_value in enumerate(vector):
        #if (feat_value < pval)and(feat_value != 0):
        if (feat_value < pval):
            features[i] = 1
    
    return features

def get_high_binary_features(rna_pval, rna_sides, pval_cutoff=.05):
    """Takes as input two vectors, one of p-values and one of sides, and transforms them in a vector of binary values.
       In this vector, 0 means that p-value(feature) > cut-off,
       and             1 means that p-value(feature) < cut-off and side == 'high'.
       This means that the feature is overrepresented in the motif, above a certain threshold."""
    
    features = np.zeros( len(rna_pval), dtype=np.uint8 )
    
    # check all high features, score as 1 if the p-value is below threshold
    # otherwise feature remains at 0
    for i in range( len(rna_pval) ):
        if (rna_sides[i]=='high')&(rna_pval[i] < pval_cutoff):
            features[i] = 1
    
    return features

def get_pvalues(mrna_df):
    """Takes the dataframe of a single mRNA, where the rows are the vector containing the frequency of each motif per nucleotide
       (with the index as the nucleotide-position), and the columns are the indices of each motif.
       Returns a list of vectors containing the p-values for each motif per nucleotide position."""
    pval_list = []       # contains the list of signatures as p-values
    side_list = []      # contains the list of sides

    # get the p-value of each row while keeping the index of the mRNA
    for nt_position, win_vector in mrna_df.iterrows():
        nb_dotbs = win_vector[0]
        cur_poisson, cur_sides = mv.normalize_poisson(win_vector[1:], nb_dotbs, WIN_SIZE)
        pval_list.append( cur_poisson )
        side_list.append( cur_sides )
    return pval_list, side_list

def calculate_similarity(mrna_df, target_sign, target_sides, pval_cutoff=.05, rna_id=''):
    """Takes as input the dataframe of a single mRNA, calculates its pvalues, and returns a vector of distances/similarity
       to the passed signature, with the indices*NT_SKIP representing the nucleotide position.
       
       mrna_df          = dataframe of calculated signature (columns) for each nucleotide position (indices). First column is nb_dotbs
       target_signature = p-values of the signature that each window is being compared against
       pval_cutoff      = p-value to use to decide whether a feature is "important" or not"""
    
    # get p-values and translate to 1/0 feature-scoring system
    rna_pval, rna_sides = get_pvalues(mrna_df)
    feature_values = []
    for i in range( len(rna_pval) ):
        #feature_values.append( get_high_binary_features( rna_pval[i], rna_sides[i], pval_cutoff ) )
        # use only first 100 motifs
        feature_values.append( get_high_binary_features( rna_pval[i][:100], rna_sides[i][:100], pval_cutoff ) )
    
    #feature_values = [ get_high_binary_features(win_pval, win_sides, pval_cutoff) for win_pval, win_sides in mrna_pval_and_sides ]
    
    # translate target signature to 1/0 feature-scoring system as well
    #target_features = get_high_binary_features(target_sign, target_sides, pval_cutoff)
    # use only first 100 motifs
    target_features = get_high_binary_features(target_sign[:100], target_sides[:100], pval_cutoff)
    
    jacc_values = [ get_jaccard_index(win_vector, target_features) for win_vector in feature_values ]
    
    if rna_id:
        return (jacc_values, mrna_df.index.values, rna_id)
    else:
        return (jacc_values, mrna_df.index.values)

if __name__ == '__main__':
    class TimeCounter:
        '''Object used for multithreading'''
        def __init__(self, target):
            self.target = target                # how many TimeCounters must be used
            self.count = 0                      # how many TimeCounters have been used
                                                # in this case, this corresponds to the number of transcripts processed
            self.similarity_dict = {}           # dictionary stores distance per nucleotide, with rna_id as indices

        def print_progress(self, met_result):
            jacc_val, nt_indices, rna_id = met_result
            
            # add resulting similarity vector to similarity dictionary
            jacc_val_df = pd.DataFrame(jacc_val, index=nt_indices).transpose()
            self.similarity_dict[ rna_id ] = jacc_val_df
            
            self.count += 1                     # keeps track of number of RNAs processed
            
            # prints current status
            if self.count % 100 == 0 or self.count == self.target:
                print(f'{dt.now() - start_time}\t{self.count}')
                
                ## keep track of execution time
                #with open(f'/u/floresj/Transcriptome_scanning_apta21/Distances/distance_measuring_{FILE_NUMBER}', 'a') as fp:
                #    fp.write(f'{dt.now() - start_time}\t{self.count}\n')
            
            # logs into file to keep track
            if self.count % 500 == 0 or self.count == self.target or self.count == 1:
                with open(f'/u/floresj/Scripts_log/log_distance_file{FILE_NUMBER}.txt', 'w') as fp:
                    fp.write(f'Subset\t{FILE_NUMBER}\n')
                    fp.write(f'Processed {self.count} out of {self.target}\n')
    
    # retrieve the DF of motifs from file
    print('Loading file...')
    df = pd.read_parquet(f'/u/floresj/mRNA_norm/mRNA_vectors/mrna_folded_int_subset{FILE_NUMBER}')
    print('File has loaded.')
    df_indices = sorted( list( {rna_id for rna_id, _ in df.index.values} ) )
    
    # calculate the p-values for aptamer-21
    seq_list = [seq for seq in parse('/u/floresj/Transcriptome_scanning_apta21/aptamer_21.fa', format='fasta')]
    apt_21 = seq_list[0]
    dotbs, shapes = mv.dotbs_and_shapes(apt_21.seq)
    a21tmp_signvec, nb_dotbs, _, _ = mv.shape60_ncm40_ncmexp500_expseq340_nodiv(apt_21.seq, dotbs, shapes)
    apt21_signvec, sides = mv.normalize_poisson(a21tmp_signvec, nb_dotbs, len(apt_21.seq))
    
    ## keep track of execution time
    print('Version: Thursday July 26, 2018')
    print('Time\t\tProcessed')
    start_time = dt.now()
    
    # multiprocessing setup
    multiprocessing.set_start_method('spawn')
    compteur = TimeCounter(len(df_indices))
    pool = multiprocessing.Pool(20)
    
    # process all transcripts
    for ind in df_indices:
        pool.apply_async(calculate_similarity, (df.loc[ind], apt21_signvec, .05, ind), callback=compteur.print_progress)
        df.drop(ind, inplace=True)
#        print(ind)
#        compteur.print_progress( calculate_similarity(df.loc[ind], apt21_signvec, .05, ind) )
    
    pool.close()
    pool.join()
    
    # save all similarity vectors in a file
    # tranposed because parquet must have string column names
    similarities = pd.concat(compteur.similarity_dict)
    
    #similarities.to_parquet('/u/floresj/Transcriptome_scanning_apta21/Distances/similarity_measuring_example.pq')
    similarities.to_csv(f'/u/floresj/Transcriptome_scanning_apta21/Distances/similarities_subset{FILE_NUMBER}.csv')