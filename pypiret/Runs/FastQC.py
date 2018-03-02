#! /usr/bin/env python

"""Check design."""
from __future__ import print_function
import os
import luigi
from luigi import ExternalTask
from luigi import LocalTarget
from luigi import Parameter, DictParameter, ListParameter, IntParameter
# from luigi.contrib.sge import SGEJobTask
from luigi import WrapperTask
from itertools import chain
from plumbum.cmd import FaQCs, cat


class RefFile(ExternalTask):
    """An ExternalTask like this."""

    path = Parameter()

    def output(self):
        """Check."""
        return LocalTarget(os.path.abspath(self.path))


class PairedRunQC(luigi.Task):
    """Running FaQCs."""

    fastqs = ListParameter()
    sample = Parameter()
    numCPUs = IntParameter()
    qc_outdir = Parameter()
    bindir = Parameter()
    faqc_min_L = IntParameter()
    n_cutoff = IntParameter()

    def requires(self):
        """Require pair of fastq."""
        if isinstance(self.fastqs, (list, tuple)):
            for fqs in self.fastqs:
                fqs_list = fqs.split(",")
                for fq in fqs_list:
                    return RefFile(fq)
        elif isinstance(self.fastqs, str):
            return RefFile(self.fastqs.split(":")[0])

    def output(self):
        """QC output."""
        out_file = self.qc_outdir + "/" + self.sample + ".stats.txt"
        return LocalTarget(out_file)

    def run(self):
        """Run the FaQC script."""
        faqc_options = ["-min_L", self.faqc_min_L,
                        "-n", self.n_cutoff,
                        "-q", "15",
                        "-lc", "0.7",
                        "-t", self.numCPUs,
                        "-prefix", self.sample,
                        "-d", os.path.abspath(self.qc_outdir),
                        "-1", self.fastqs[0],
                        "-2", self.fastqs[1]]
        faqc_cmd = FaQCs[faqc_options]
        faqc_cmd()

    def program_environment(self):
        """Environmental variables for this program."""
        return {'PATH': os.environ["PATH"] + ":" + self.bindir}

# class SGEPairedRunQC(SGEJobTask):
#     """Running the perl script for QC."""
#     # TODO: Waiting on a response from luigi group

#     fastqs = ListParameter()
#     sample = Parameter()
#     qc_outdir = Parameter()
#     parallel_env = "smp"
#     no_tarball = True
#     dont_remove_tmp_dir = True
#     job_name_format = "{sample}_{task_family}"

#     def requires(self):
#         """Require pair of fastq."""
#         return [RefFile(self.fastqs[0])]

#     def output(self):
#         """QC output."""
#         return LocalTarget(self.qc_outdir + "/" + self.sample + ".stats.text")

#     # def run_program(self):
#     #     subprocess.call(["perl", "scripts/illumina_fastq_QC.pl",
#     #                     "-min_L", "60",
#     #                     "-n", "5",
#     #                       "-q", "15",
#     #                       "-lc", "0.7",
#     #                       "-t", str(self.n_cpu),
#     #                       "-prefix", str(self.sample),
#     #                       "-d", str(os.path.abspath(self.qc_outdir)),
#     #                       "-p", str(self.fastqs)], shell=True, stdout=subprocess.PIPE,
#     #                       stderr=subprocess.PIPE)

#     def work(self):
#         """Run the perl script."""
#         # logger.info('Running test job...')
#         # mig = os.path.abspath(self.qc_outdir)
#         out_file = self.qc_outdir + "/" + self.sample + ".stats.txt"
#         # out_file_full = mig + "/" + self.sample + ".stats.text"
#         subprocess.call(["ls", "-lh"])
#         # with open(out_file, 'w') as f:
#         # f.write('this is a test')

#         # self.run_program()

#         # subprocess.call(["perl", "scripts/illumina_fastq_QC.pl",
#         #                 "-min_L", "60",
#         #                 "-n", "5",
#         #                   "-q", "15",
#         #                   "-lc", "0.7",
#         #                   "-t", str(self.numCPUs),
#         #                   "-prefix", str(self.sample),
#         #                   "-d", str(os.path.abspath(self.qc_outdir)),
#         #                   "-p", str(self.fastqs)], shell=True, stdout=subprocess.PIPE,
#         #                   stderr=subprocess.PIPE)


class RunAllQC(WrapperTask):
    """Run all QC."""

    fastq_dic = DictParameter()
    workdir = Parameter()
    numCPUs = IntParameter()
    bindir = Parameter()
    faqc_min_L = IntParameter()
    n_cutoff = IntParameter()

    def requires(self):
        """A wrapper for running the QC."""
        for samp, fastq in self.fastq_dic.items():
            trim_dir = self.workdir + "/" + samp + "/trimming_results"
            if os.path.isdir(trim_dir) is False:
                os.makedirs(trim_dir)
            if isinstance(fastq, (list, tuple)):
                fqs = [fq.replace(';', ',') for fq in fastq]
                i = 1
                for fq in fqs:
                    fq_list = fq.split(",")
                    cp_fq = trim_dir + "/" + samp + "_R" + str(i) + ".fastq"
                    cat_cmd = (cat[fq_list] > cp_fq)
                    cat_cmd()
                    i = i + 1
                yield PairedRunQC(fastqs=[trim_dir + "/" + samp +
                                          "_R1.fastq", trim_dir + "/" +
                                          samp + "_R2.fastq"],
                                  sample=samp,
                                  numCPUs=self.numCPUs,
                                  qc_outdir=trim_dir,
                                  bindir=self.bindir,
                                  faqc_min_L=self.faqc_min_L,
                                  n_cutoff=self.n_cutoff)

            else:
                if os.path.isdir(trim_dir) is False:
                    os.makedirs(trim_dir)
                fqs = [os.path.abspath(fq) for fq in fastq.split(":")]
                yield PairedRunQC(fastqs=fqs,
                                  sample=samp,
                                  numCPUs=self.numCPUs,
                                  qc_outdir=trim_dir,
                                  bindir=self.bindir,
                                  faqc_min_L=self.faqc_min_L,
                                  n_cutoff=self.n_cutoff)


# class SGERunAllQC(WrapperTask):
#     """Run all QC."""

#     fastq_dic = DictParameter()
#     workdir = Parameter()
#     numCPUs = IntParameter()
#     shared_tmp_dir = Parameter()

#     def requires(self):
#         """A wrapper for running the QC."""
#         for samp, fastq in self.fastq_dic.iteritems():
#             trim_dir = self.workdir + "/" + samp + "/trimming_results"
#             if isinstance(fastq, (list, tuple)):
#                 fqs = list(chain.from_iterable(
#                     [fq.split(':') for fq in fastq]))
#                 print(fqs)
#                 if os.path.isdir(trim_dir) is False:
#                     os.makedirs(trim_dir)
#                 yield SGEPairedRunQC(fastqs=fqs,
#                                      sample=samp,
#                                      n_cpu=self.numCPUs,
#                                      qc_outdir=trim_dir,
#                                      shared_tmp_dir=self.shared_tmp_dir)

#             else:
#                 if os.path.isdir(trim_dir) is False:
#                     os.makedirs(trim_dir)
#                 fqs = [os.path.abspath(fq) for fq in fastq.split(":")]
#                 yield SGEPairedRunQC(fastqs=fqs,
#                                      sample=samp,
#                                      n_cpu=self.numCPUs,
#                                      qc_outdir=trim_dir,
#                                      shared_tmp_dir=self.shared_tmp_dir)
