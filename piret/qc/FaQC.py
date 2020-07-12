#! /usr/bin/env python

"""Check design."""
from __future__ import print_function
import os
import sys
import logging
import luigi
import pandas as pd
from itertools import chain
from luigi import ExternalTask
from luigi import LocalTarget
from luigi import Parameter, DictParameter, ListParameter
from luigi import IntParameter
from luigi.util import inherits, requires
from itertools import chain
from plumbum.cmd import FaQCs, cat


class RefFile(ExternalTask):
    """An ExternalTask to check if file exist."""
    path = Parameter()

    def output(self):
        """Check."""
        return LocalTarget(os.path.abspath(self.path))


class PairedRunQC(luigi.Task):
    """Running FaQCs."""
    fastqs = ListParameter()
    sample = Parameter()
    num_cpus = IntParameter()
    workdir = Parameter()
    faqc_min_L = IntParameter()
    avg_q = IntParameter()
    n_cutoff = IntParameter()

    def requires(self):
        """Require pair of fastq."""
        if isinstance(self.fastqs, (list, tuple)):
            for fqs in self.fastqs:
                fqs_list = fqs.split(",")
                for f_q in fqs_list:
                    return RefFile(f_q)
        elif isinstance(self.fastqs, str):
            return RefFile(self.fastqs.split(":")[0])

    def output(self):
        """QC output."""
        trim_dir = os.path.join(self.workdir, "processes", "qc", self.sample)
        out_file = trim_dir + "/" + self.sample + ".stats.txt"
        return LocalTarget(out_file)

    def run(self):
        """Run the FaQC script."""
        trim_dir = os.path.join(self.workdir, "processes", "qc", self.sample)
        faqc_options = ["-min_L", self.faqc_min_L,
                        "-n", self.n_cutoff,
                        "-t", self.num_cpus,
                        "-avg_q", self.avg_q,
                        "-prefix", self.sample,
                        "-d", os.path.abspath(trim_dir),
                        "-1", self.fastqs[0],
                        "-2", self.fastqs[1]]
        faqc_cmd = FaQCs[faqc_options].run(retcode=None)
        logger = logging.getLogger('luigi-interface')
        logger.info(faqc_cmd)


class RunAllQC(luigi.WrapperTask):
    """Wrapper task to Run all QC."""

    fastq_dic = DictParameter()
    workdir = Parameter()
    num_cpus = IntParameter()
    faqc_min_L = IntParameter()
    avg_q = IntParameter()
    n_cutoff = IntParameter()

    def requires(self):
        """A wrapper for running the QC."""
        for samp, fastq in self.fastq_dic.items():
            trim_dir = os.path.join(self.workdir, "processes", "qc", samp)
            if os.path.isdir(trim_dir) is False:
                os.makedirs(trim_dir)
            if isinstance(fastq, (list, tuple)):
                fqs = [fq.replace(';', ',') for fq in fastq]
                r1_list = [f.split(":")[0] for f in fqs]
                r2_list = [f.split(":")[1] for f in fqs]
                r1_fq = trim_dir + "/" + samp + "_R1" + ".fastq"
                r2_fq = trim_dir + "/" + samp + "_R2" + ".fastq"
                cat_cmd_r1 = (cat[r1_list] > r1_fq)
                cat_cmd_r2 = (cat[r2_list] > r2_fq)
                cat_cmd_r1()
                cat_cmd_r2()
                yield PairedRunQC(fastqs=[trim_dir + "/" + samp +
                                          "_R1.fastq", trim_dir + "/" +
                                          samp + "_R2.fastq"],
                                  sample=samp,
                                  num_cpus=self.num_cpus,
                                  workdir=self.workdir,
                                  faqc_min_L=self.faqc_min_L,
                                  avg_q=self.avg_q,
                                  n_cutoff=self.n_cutoff)

            else:
                if os.path.isdir(trim_dir) is False:
                    os.makedirs(trim_dir)
                fqs = [os.path.abspath(fq) for fq in fastq.split(":")]
                yield PairedRunQC(fastqs=fqs,
                                  sample=samp,
                                  num_cpus=self.num_cpus,
                                  workdir=self.workdir,
                                  faqc_min_L=self.faqc_min_L,
                                  avg_q=self.avg_q,
                                  n_cutoff=self.n_cutoff)


@requires(RunAllQC)
class SummarizeQC(luigi.Task):
    """Summarizes FaQC results of all samples into a table"""

    def output(self):
        """QC output."""
        out_file = os.path.join(self.workdir, "processes", "qc",
                                "QCsummary.csv")
        return LocalTarget(out_file)

    def run(self):
        """Parse the FaQC stats."""
        summ_dic = {}

        for samp, fastq in self.fastq_dic.items():
            trim_dir = os.path.join(self.workdir, "processes", "qc", samp)
            filename = os.path.join(trim_dir, samp + ".stats.txt")
            with open(filename, 'r') as file:
                lines = file.readlines()
                reads_before_trimming = lines[1].split(":")[1].strip()
                read_length = lines[3].split(":")[1].strip()
                reads_aft_trim = lines[9].split(":")[1].split("(")[0].strip()
                summ_dic[samp] = [read_length,
                                  reads_before_trimming,
                                  reads_aft_trim]
        summ_table = pd.DataFrame.from_dict(summ_dic, orient='index')
        summ_table.columns = ["Read Length", "Raw reads", "Reads after QC"]
        out_file = os.path.join(self.workdir, "processes", "qc",
                                "QCsummary.csv")
        summ_table.to_csv(out_file)
