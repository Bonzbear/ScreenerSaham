import requests
import pandas as pd

url = "https://www.idx.co.id/primary/ListedCompany/GetCompanyProfiles"

headers = {
    "User-Agent": "Mozilla/5.0"
}

r = requests.get(url, headers=headers)
data = r.json()

df = pd.DataFrame(data["Data"])

print(df.head())
print("Total emiten:", len(df))
