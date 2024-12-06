import json
from pathlib import Path
from requests import request
import pandas as pd

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()

origins = [
  "http://localhost",
  "http://localhost:1420",
  "http://localhost:5050",
  "https://pro.openbb.dev",
  "https://pro.openbb.co",
  "https://excel.openbb.co",
  "https://excel.openbb.dev",
]

app.add_middleware(
  CORSMiddleware,
  allow_origins=origins,
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)


@app.get("/")
def read_root():
  return {"Info": "Terrapin Example for OpenBB"}


@app.get("/widgets.json")
def get_widgets():
  """Widgets configuration file for OpenBB Pro"""
  return JSONResponse(
    content=json.load((Path(__file__).parent.resolve() / "widgets.json").open())
  )


@app.get("/debt_payment_schedule")
def get_debt_payment_schedule(payment_type: str = None):
  headers = {
    "Authorization": f"Bearer {os.getenv('TERRAPIN_API_KEY')}",
    "Content-Type": "application/json"
  }

  body = {
    "leis": ["ECTRVYYCEF89VWYS6K36"], # UK gov LEI
    "interest_types": ["fixed rate"]
  }


  try:
    bond_search = request("POST", "https://terrapinfinance.com/api/v1/bond_search", json=body, headers=headers).json()["data"]

    isins = [bond["isin"] for bond in bond_search]
    bonds_reference = request("POST", "https://terrapinfinance.com/api/v1/bond_reference", json={"isins": isins}, headers=headers).json()["data"]
    bonds_by_isin = {bond["isin"]: bond for bond in bonds_reference}
    cashflows = request("POST", "https://terrapinfinance.com/api/v1/bond_cashflows", json={"isins": list(bonds_by_isin.keys())}, headers=headers).json()["data"]

    future_cashflows = [
      {"amount": c["amount"] * bonds_by_isin[c["isin"]]["issued_amount"] / 100 / 1_000_000_000, "date": c["date"], "type": c["type"]}
      for c in cashflows if c["date"] > "2024-12-01"
    ]

    if payment_type == "interest":
      future_cashflows = [c for c in future_cashflows if c["type"] == "interest"]
    elif payment_type == "principal":
      future_cashflows = [c for c in future_cashflows if c["type"] == "principal"]
    elif payment_type == "total":
      pass

    df = pd.DataFrame(future_cashflows)

    # Extract year from date
    df['date'] = pd.to_datetime(df['date'])
    df['year'] = df['date'].dt.to_period('Y').astype(str)

    # Aggregate by year and type
    grouped = df.groupby(['year', 'type']).sum(numeric_only=True).reset_index()
    data_dict = grouped.pivot(index='year', columns='type', values='amount').fillna(0.0).reset_index().to_dict(orient="records")

    return data_dict
  except Exception as err:
    print(f"Programming Error: {err}")
    return JSONResponse(content={"error": err}, status_code=500)
