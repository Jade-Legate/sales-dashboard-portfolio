# Data attribution (NOTICE)

`data_penjualan.csv` is a third-party dataset redistributed under the Apache License 2.0
(full text: `LICENSE-APACHE-2.0.txt`).

- **Title:** Data Penjualan Produk Cetakan
- **Author:** Jabir Muktabir
- **Source:** https://www.kaggle.com/datasets/jabirmuktabir/data-penjualan-produk-cetakan
- **License:** Apache License 2.0
- **Description (from source):** daily sales records of a printing company, August 2022 - November 2023;
  sensitive company information was removed by the author before publication.

## Changes made in this repository

The file `data_penjualan.csv` itself is **unmodified**. All derived data are produced by code in this
repository and are stored separately (`data/sales.db`, generated, not committed):

- product-name standardization into product families, duplicate-candidate flagging,
- a business-unit grouping of product families (an assumption made by this project, not in the source),
- a simulated monthly target derived from the trailing three-month average (not in the source).

The author of this dataset is not affiliated with, and does not endorse, this project.
