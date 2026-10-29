from etl.errors import UnsupportedFormatError
from etl.loader import DataLoader

sample = [{"id": 1, "name": "Amina"}, {"id": 2, "name": "Brian"}]

print(DataLoader("output/scratch_test/sample.csv").load(sample))
print(DataLoader("output/scratch_test/sample.json").load(sample))

try:
    DataLoader("output/sample.xlsx")
except UnsupportedFormatError as exc:
    print("caught:", exc)