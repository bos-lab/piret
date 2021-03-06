#! /usr/bin/env python

"""Check design."""
import os
import sys
import luigi
import shutil
from luigi import LocalTarget
from luigi.util import inherits, requires
import pandas as pd
DIR = os.path.dirname(os.path.realpath(__file__))
script_dir = os.path.abspath(os.path.join(DIR, "../../scripts"))
os.environ["PATH"] += ":" + script_dir
sys.path.insert(0, script_dir)
from plumbum.cmd import Rscript, plot_pathway
from plumbum.cmd import RDESeq2, gage_analysis
import logging


class DESeq2(luigi.Task):
    """Find DGE using DESeq2."""
    workdir = luigi.Parameter()
    exp_design = luigi.Parameter()
    p_value = luigi.FloatParameter()
    kingdom = luigi.Parameter()
    # GAGE = luigi.BoolParameter()
    # pathway = luigi.BoolParameter()
    # gff_file = luigi.Parameter()

    def output(self):
        """Expected output of DGE using DESeq2."""
        deseq_dir = os.path.join(self.workdir, "processes", "DESeq2",
                                 self.kingdom)
        out_filepath = os.path.join(deseq_dir, "summary_updown.csv")
        return LocalTarget(out_filepath)

    def run(self):
        """Run DESeq2."""
        fcount_dir = os.path.join(self.workdir, "processes", "featureCounts", self.kingdom)
        DESeq2_dir = os.path.join(self.workdir, "processes", "DESeq2", self.kingdom)
        if not os.path.exists(DESeq2_dir):
            os.makedirs(DESeq2_dir)
        for file in os.listdir(fcount_dir):
            if file.endswith("tsv"):
                feat_name = file.split("_")[-2]
                # only run deseq on gene and CDS
                if any(feat == feat_name for feat in ["CDS", "gene", "rRNA", "tRNA", "exon", "transcript"]) is True:
                    deseq2_list = ["-r", os.path.join(fcount_dir, file),
                                  "-e", self.exp_design, "-p", self.p_value,
                                  "-n", feat_name,
                               "-o", DESeq2_dir]
                    deseq2_cmd = RDESeq2[deseq2_list]
                    logger = logging.getLogger('luigi-interface')
                    logger.info(deseq2_cmd)
                    deseq2_cmd()
            # if file == "gene_count.tsv":
            #     if self.prok_org_code is None:
            #         org_code=self.euk_org_code
            #     else:
            #         org_code=self.prok_org_code
            #     if self.pathway is True:
            #         path_list = ["-d", DESeq2_dir,
            #              "-m", "DESeq2", "-c",
            #              org_code] # get pathway information
            #         path_cmd = plot_pathway[path_list]
            #         logger.info(path_cmd)
            #         path_cmd()
            #     if self.GAGE is True:
            #         gage_list = ["-d", DESeq2_dir, "-m",
            #              "DESeq2", "-c", self.org_code]
            #         gage_cmd = gage_analysis[gage_list]
            #         logger.info(gage_cmd)
            #         gage_cmd()
        self.summ_summ()

    def summ_summ(self):
        """Summarize the summary table to be displayed in edge"""
        deseq_dir = os.path.join(self.workdir, "processes",
                                 "DESeq2", self.kingdom)
        all_dirs = os.listdir(deseq_dir)
        if all_dirs:
            out_file = os.path.join(deseq_dir, "summary_updown.csv")
            summ_files = []
            for root, dirs, files in os.walk(deseq_dir):
                for file in files:
                    if "summary.csv" in file:
                        summ_files.append(os.path.join(root, file))
            summ_df = [pd.read_csv(file, index_col=0) for file in summ_files]
            summ_df_ccat = pd.concat(summ_df)
            summ_df_ccat.to_csv(out_file)
