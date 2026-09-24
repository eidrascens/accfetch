# SRA Retrieval Pipeline

A Python pipeline for downloading sequencing runs from NCBI SRA, DDBJ,
and ENA, converting them to compressed FASTQ for downstream meta-analysis
of genomic and transcriptomic data. Designed for batch processing of
multiple studies on HPC clusters.


# Features

- Fetches runs from a Study or BioProject accession
- Downloads `.sra` via `prefetch`
- Converts to FASTQ via `fasterq-dump`
- Compresses via `pigz`
- Cleans up `.sra` and empty subdirectories
- Supports NCBI SRA, DDBJ, and ENA accessions

| Source | Project | Study | Run |
| :--- | :--- | :--- | :--- |
| NCBI SRA | `PRJNA...` | `SRP...` | `SRR...` |
| DDBJ | `PRJDB...` | `DRP...` | `DRR...` |
| ENA | `PRJEB...` | `ERP...` | `ERR...` |

---

# Design Choices

A few deliberate choices shape how this pipeline behaves:

- **Per-project output layout.** FASTQ files are organized under a
  folder named after each BioProject. This keeps runs from different
  studies separated, which is helpful when assembling a
  multi-project meta-analysis.

- **Resume-safe.** Interrupted jobs can be resubmitted safely.
  Completed runs are detected and skipped, so no work is repeated.

- **HPC-native scratch handling.** Temporary files produced during
  FASTQ conversion are directed to a scratch directory rather than
  the project folder or `$HOME`, keeping quota usage low.

- **External compression.** Compression is performed as a separate
  post-conversion step, which also allows alternative compressors
  to be swapped in if needed.

# References

- [SRA Toolkit Wiki](https://github.com/ncbi/sra-tools/wiki)
- [fasterq-dump Guide](https://github.com/ncbi/sra-tools/wiki/HowTo:-fasterq-dump)
- [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
- [SLURM Documentation](https://slurm.schedmd.com/documentation.html)

# Contributors

Developed and maintained jointly by `eidrascens` and `gerryjr.ramos`.

# Acknowledgments

Testing and validation were performed on the **saliksik HPC cluster**
operated by the **Advanced Science and Technology Institute (ASTI)**,
Department of Science and Technology (DOST), Philippines.
