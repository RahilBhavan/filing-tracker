# Source access and provenance

The initial SEC download attempt returned HTTP 403. V2 uses five successfully downloaded **official issuer copies**. They are not claimed to be byte-identical to SEC HTML. All downloads occurred September 21, 2026; original and converted SHA-256 hashes are recorded in the pair manifests.

| Issuer / FY | Official source | Period ended | Filed | SEC accession |
| --- | --- | --- | --- | --- |
| Microsoft 2022 | [DOCX](https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/MSFT_FY22Q4_10K) | 2022-06-30 | 2022-07-28 | 0001564590-22-026876 |
| Microsoft 2023 | [DOCX](https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/MSFT_FY23Q4_10K) | 2023-06-30 | 2023-07-27 | 0000950170-23-035122 |
| Microsoft 2024 | [DOCX](https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/MSFT_FY24Q4_10K) | 2024-06-30 | 2024-07-30 | 0000950170-24-087843 |
| Berkshire 2023 | [PDF](https://www.berkshirehathaway.com/2023ar/202310-k.pdf) | 2023-12-31 | 2024-02-26 | 0000950170-24-019719 |
| Berkshire 2024 | [PDF](https://www.berkshirehathaway.com/2024ar/202410-k.pdf) | 2024-12-31 | 2025-02-24 | 0000950170-25-025210 |

Microsoft download-center links: [2022](https://www.microsoft.com/investor/reports/ar22/download-center/), [2023](https://www.microsoft.com/investor/reports/ar23/download-center/), [2024](https://www.microsoft.com/investor/reports/ar24/download-center/). Berkshire annual menus: [2023](https://www.berkshirehathaway.com/2023ar/linksannual23.html), [2024](https://www.berkshirehathaway.com/2024ar/linksannual24.html). SEC index URLs are preserved in each manifest.

## Conversion boundaries

DOCX conversion reads original XML paragraphs and table cells with Python's standard library. PDF conversion uses `pdftotext -bbox-layout`, keeping the page, block, and bounding box. Every extracted block stores its original locator. Normalized offsets refer to the extracted text, not original byte offsets.

PDF tables may become separate column blocks; paragraphs spanning pages remain separate. Neither converter resolves accounting semantics. A visual check of Berkshire 2024 PDF page 27 confirmed readable paragraph/heading order; automated tests validate every extracted block against normalized source offsets. This is not an exhaustive visual audit of all 282 combined PDF pages.

Original files are in `corpus/originals/`; converted HTML is in `corpus/converted/`. Comparison loading verifies both original and converted hashes. The original fictional Alder corpus is retained only for regression testing.
