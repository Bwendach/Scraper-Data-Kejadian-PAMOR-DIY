import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re

BASE_URL = "https://pamor.jogjaprov.go.id"
LIST_URL = f"{BASE_URL}/data_kejadian"

session = requests.Session()


def get_csrf():
    """Fetch CSRF token from list page."""
    res = session.get(LIST_URL)
    soup = BeautifulSoup(res.text, "html.parser")
    token = soup.find("meta", {"name": "csrf-token"})
    return token["content"] if token else None


def get_list_data(csrf, start_date, end_date, page=1):
    """Fetch one list page and extract summary rows."""
    payload = {
        "frontend-csrf": csrf,
        "TicketSearch[id_jenis_kejadian]": '6',
        "TicketSearch[id_kabupaten]": '1',
        "TicketSearch[tanggal_kejadian]": start_date,
        "TicketSearch[tanggal_kejadian_end]": end_date,
        "page": page
    }

    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": LIST_URL
    }

    url = f"{LIST_URL}?page={page}"
    res = session.post(url, data=payload, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    rows = soup.select("tbody tr")
    results = []

    for row in rows:
        cols = row.find_all("td")
        link = row.find("a")

        if len(cols) >= 10 and link:
            id_ = link.get("href").split("/")[-1]

            results.append({
                "id": id_,
                "kode": cols[1].get_text(strip=True),
                "jenis": cols[2].get_text(strip=True),
                "spesifikasi": cols[3].get_text(strip=True),
                "kabupaten": cols[4].get_text(strip=True),
                "kecamatan": cols[5].get_text(strip=True),
                "kelurahan": cols[6].get_text(strip=True),
                "dusun": cols[7].get_text(strip=True),
                "rt_rw": cols[8].get_text(strip=True),
            })

    return results, res.text

def get_detail(id_):
    """Fetch detail page HTML by event ID."""
    url = f"{BASE_URL}/data_kejadian/detail/{id_}"
    res = session.get(url)
    return res.text


def extract_coords(text):
    """Extract latitude and longitude from detail text."""
    lat = re.search(r"Latitude\s*:\s*([-0-9.]+)", text)
    lon = re.search(r"Longitude\s*:\s*([-0-9.]+)", text)

    return (
        float(lat.group(1)) if lat else None,
        float(lon.group(1)) if lon else None
    )


def parse_detail(html):
    """Parse key/value fields from detail page table."""
    soup = BeautifulSoup(html, "html.parser")
    data = {}

    rows = soup.select("table tbody tr")

    for row in rows:
        cols = row.find_all("td")

        if len(cols) >= 3:
            key = cols[0].get_text(strip=True)
            # Keep text readable even when HTML has nested tags or line breaks.
            value = cols[2].get_text(separator=" ", strip=True)

            if key:
                data[key] = value

    # Add parsed coordinates as dedicated numeric columns.
    coords = data.get("Koordinat", "")
    lat, lon = extract_coords(coords)

    data["latitude"] = lat
    data["longitude"] = lon

    return data

def get_total_pages(html):
    soup = BeautifulSoup(html, "html.parser")

    pages = soup.select(".pagination li a")

    max_page = 1

    for p in pages:
        text = p.get_text(strip=True)
        if text.isdigit():
            max_page = max(max_page, int(text))

    return max_page


def clean_text(val):
    """Normalize text and prevent CSV/Excel formula injection."""
    if isinstance(val, str):
        val = val.strip()

        # Remove placeholder-like values only when exact match.
        if val in ["#NAME?", "", None]:
            return None

        # Prevent spreadsheet formula execution on open.
        if val.startswith(("=", "+", "-", "@")):
            val = "'" + val

    return val


def main():
    """Run scraping, cleaning, and CSV export."""
    csrf = get_csrf()

    if not csrf:
        print("Failed to get CSRF token")
        return

    all_data = []

    for year in range(2025, 2026):
        print(f"\n=== YEAR {year} ===")

        start = f"01/12/{year}"
        end = f"31/12/{year}"

        seen_ids = set()

        # First request is used to detect pagination count.
        rows, html = get_list_data(csrf, start, end, page=1)

        total_pages = get_total_pages(html)
        print(f"Total pages: {total_pages}")

        for page in range(1, total_pages + 1):
            print(f"\nPage {page}")

            rows, _ = get_list_data(csrf, start, end, page)

            for row in rows:
                if row["id"] in seen_ids:
                    continue

                seen_ids.add(row["id"])

                print(f"→ Scraping ID {row['id']}")

                try:
                    html_detail = get_detail(row["id"])
                    detail = parse_detail(html_detail)

                    combined = {**row, **detail}
                    all_data.append(combined)

                except Exception as e:
                    print(f"Error: {e}")

                time.sleep(0.5)

    df = pd.DataFrame(all_data)

    # Drop fields not needed in final dataset.
    df = df.drop(columns=[
        "Koordinat",
        "Status",
        "Lokasi",
        "No Ticket",
        "Jenis Kejadian",
        "Spesifikasi Kejadian"
    ], errors="ignore")


    # Split "Waktu" into date and time columns.
    df["Waktu"] = df["Waktu"].str.strip()

    df[["tanggal", "jam"]] = df["Waktu"].str.split(" ", expand=True)

    # Convert date to datetime for consistent parsing.
    df["tanggal"] = pd.to_datetime(df["tanggal"], dayfirst=True, errors="coerce")

    # Remove original combined time field.
    df = df.drop(columns=["Waktu"])


    # Keep RT/RW as text so spreadsheet tools do not auto-convert it.
    df["rt_rw"] = df["rt_rw"].astype(str)

    # Remove known placeholder values.
    df = df.replace("#NAME?", None)

    # Trim surrounding spaces from all object columns.
    df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    
    cols_to_clean = ["Kronologi", "Penyebab", "Pemicu"]

    for col in cols_to_clean:
        if col in df.columns:
            df[col] = df[col].apply(clean_text)

    # Save cleaned output.
    df.to_csv("kejadian_clean.csv", index=False)

    print("Cleaned data saved to kejadian_clean.csv")
    
    
if __name__ == "__main__":
    main()