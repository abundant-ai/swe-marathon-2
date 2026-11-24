# SO-101 frame table excerpt

The source is [SO-101 cube pick-and-place (D1, v1) by lsalomme](https://huggingface.co/datasets/lsalomme/so101-d1v1-cube-pick-place).
The author distributes the dataset under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The packaged Parquet excerpt takes rows 75–122 inclusive from
data/chunk-000/file-000.parquet and rewrites them as a smaller Parquet file.
The tabular values and native schema are preserved. No video, audio, or images
from the original recording enter the fixture.

The downloaded source shard had SHA-256
340ec20a2d0f4027c684708fed3493c6b67eae6ad9bebcd9314de36ab0d2bbd9.
The packaged excerpt has SHA-256
e58a74e93ebb7ec34fb490c2e08815bb5ce30333af094cd550c2a8010f3bbe50.
