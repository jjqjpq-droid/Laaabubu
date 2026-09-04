#!/usr/bin/env python3

import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET

from flask import Flask, jsonify, request
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

BASE_URL = "https://vahan.parivahan.gov.in"
HOMEPAGE_URL = f"{BASE_URL}/vahanservice/vahan/ui/statevalidation/homepage.xhtml"

def create_session_with_retries():
    session = requests.Session()
    retry = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

AJAX_HEADERS = {
    "Accept": "application/xml, text/xml, */*; q=0.01",
    "Faces-Request": "partial/ajax",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": BASE_URL,
}

def levi_extract_viewstate(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    vs_el = soup.find("input", {"name": "javax.faces.ViewState"})
    if vs_el and vs_el.get("value"):
        return vs_el["value"]
    m = re.search(r'name=["\']javax\.faces\.ViewState["\'][^>]*value=["\']([^"\']+)["\']', html_text)
    if m:
        return m.group(1)
    raise ValueError("Failed to extract initial javax.faces.ViewState from HTML.")

def eren_extract_viewstate_from_xml(xml_text, fallback_vs=""):
    try:
        root = ET.fromstring(xml_text)
        for upd in root.findall(".//update"):
            if "ViewState" in upd.get("id", ""):
                if upd.text:
                    return upd.text.strip()
    except Exception:
        pass
    m = re.search(r'<update id="[^"]*ViewState[^"]*"><!\[CDATA\[(.*?)\]\]>', xml_text)
    if m:
        return m.group(1).strip()
    return fallback_vs

def mikasa_extract_redirect_url(xml_text):
    try:
        root = ET.fromstring(xml_text)
        redir = root.find(".//redirect")
        if redir is not None and redir.get("url"):
            return redir.get("url")
    except Exception:
        pass
    m = re.search(r'<redirect\s+url=["\']([^"\']+)["\']', xml_text)
    if m:
        return m.group(1)
    return ""

def armin_fetch_chassis(vehicle_no):
    vehicle_no = vehicle_no.upper().replace(" ", "")
    session = create_session_with_retries()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Origin": "https://www.smcinsurance.com",
        "Referer": "https://www.smcinsurance.com/",
    })
    try:
        session.get("https://www.smcinsurance.com/", timeout=15)
        time.sleep(1)
        payload = {"URL": "GetVaahanDetailsByVehicleNo", "Props": [vehicle_no], "Token": ""}
        headers = {
            "Content-Type": "application/json",
            "Origin": "https://www.smcinsurance.com",
            "Referer": "https://www.smcinsurance.com/",
        }
        response = session.post(
            "https://www.smcinsurance.com/central/centralcall/CallReqWithHeader",
            json=payload,
            headers=headers,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        if data.get("statusCode") == 200 and data.get("response", {}).get("chassis"):
            return data["response"]["chassis"]
        return None
    except Exception as e:
        return None

def hange_fetch_mobile(vehicle_no, chassis_no):
    clean_vehicle_no = vehicle_no.strip().upper()
    clean_chassis_no = chassis_no.strip().upper()
    if len(clean_chassis_no) > 5:
        clean_chassis_no = clean_chassis_no[-5:]

    session = create_session_with_retries()
    session.headers.update(COMMON_HEADERS)

    try:
        r1 = session.get(HOMEPAGE_URL, timeout=30)
        if r1.status_code != 200:
            raise RuntimeError(f"Failed to access Parivahan portal: status {r1.status_code}")
    except Exception as e:
        raise RuntimeError(f"Connection error: {str(e)}")

    vs = levi_extract_viewstate(r1.text)
    soup1 = BeautifulSoup(r1.text, "html.parser")
    cb = soup1.find("input", {"type": "checkbox"})
    if not cb or not cb.get("id"):
        raise RuntimeError("Could not locate agreement checkbox on homepage.")
    cb_full_id = cb["id"]
    cb_base_id = cb_full_id.replace("_input", "")

    data_cb = {
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": cb_base_id,
        "javax.faces.partial.execute": cb_base_id,
        "javax.faces.partial.render": "proccedHomeButtonId",
        "javax.faces.behavior.event": "change",
        "javax.faces.partial.event": "change",
        "homepageformid": "homepageformid",
        "regnid": clean_vehicle_no,
        f"{cb_base_id}_input": "on",
        "abc": "abc",
        "javax.faces.ViewState": vs,
        "pmtchk_input": "-1",
    }
    h_ajax = dict(AJAX_HEADERS)
    h_ajax["Referer"] = HOMEPAGE_URL

    try:
        r2 = session.post(HOMEPAGE_URL, headers=h_ajax, data=data_cb, timeout=30)
        if r2.status_code != 200:
            raise RuntimeError(f"Checkbox AJAX failed: status {r2.status_code}")
        vs = eren_extract_viewstate_from_xml(r2.text, vs)
    except Exception as e:
        raise RuntimeError(f"Checkbox step failed: {str(e)}")

    data_proceed = {
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": "proccedHomeButtonId",
        "javax.faces.partial.execute": "@all",
        "javax.faces.partial.render": "regnid facelesslist portaldownMsgPnl mainhomepagepnl leftmenupnlid leftmenupnlidservdown",
        "proccedHomeButtonId": "proccedHomeButtonId",
        "homepageformid": "homepageformid",
        "regnid": clean_vehicle_no,
        f"{cb_base_id}_input": "on",
        "abc": "abc",
        "javax.faces.ViewState": vs,
        "pmtchk_input": "-1",
    }

    try:
        r3 = session.post(HOMEPAGE_URL, headers=h_ajax, data=data_proceed, timeout=30)
        if r3.status_code != 200:
            raise RuntimeError(f"Proceed AJAX failed: status {r3.status_code}")
        vs = eren_extract_viewstate_from_xml(r3.text, vs)
    except Exception as e:
        raise RuntimeError(f"Proceed step failed: {str(e)}")

    faceless_btn_id = None
    try:
        root3 = ET.fromstring(r3.text)
        for u in root3.findall(".//update"):
            if u.get("id") == "facelesslist" and u.text:
                f_soup = BeautifulSoup(u.text, "html.parser")
                btn = f_soup.find("button")
                if btn and btn.get("id"):
                    faceless_btn_id = btn.get("id")
                    break
    except Exception:
        pass

    if not faceless_btn_id:
        m_btn = re.search(r'id=["\'](j_idt\d+)["\'][^>]*type=["\']submit["\'][^>]*><span[^>]*>[^<]*Proceed', r3.text)
        if m_btn:
            faceless_btn_id = m_btn.group(1)

    if not faceless_btn_id:
        if "Invalid" in r3.text or "not found" in r3.text.lower():
            raise RuntimeError(f"Vehicle '{clean_vehicle_no}' not recognized.")
        raise RuntimeError("Could not locate modal Proceed button.")

    data_step4 = {
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": faceless_btn_id,
        "javax.faces.partial.execute": "@all",
        faceless_btn_id: faceless_btn_id,
        "homepageformid": "homepageformid",
        "j_idt55_input": "en",
        "regnid": clean_vehicle_no,
        f"{cb_base_id}_input": "on",
        "pmtchk_input": "-1",
        "nocregnno": "",
        "javax.faces.ViewState": vs,
    }

    try:
        r4 = session.post(HOMEPAGE_URL, headers=h_ajax, data=data_step4, timeout=30)
        redir_url_1 = mikasa_extract_redirect_url(r4.text)
        if not redir_url_1:
            raise RuntimeError("No redirect URL found")
        full_redir_1 = urllib.parse.urljoin(BASE_URL, redir_url_1)
    except Exception as e:
        raise RuntimeError(f"Navigation step failed: {str(e)}")

    try:
        r5 = session.get(full_redir_1, headers={"Referer": HOMEPAGE_URL}, timeout=30)
        if r5.status_code != 200:
            raise RuntimeError(f"Login page failed: status {r5.status_code}")
    except Exception as e:
        raise RuntimeError(f"Login page error: {str(e)}")

    soup5 = BeautifulSoup(r5.text, "html.parser")
    vs = levi_extract_viewstate(r5.text)

    fitness_anchor_id = None
    for a in soup5.find_all("a"):
        oc = a.get("onclick", "")
        if "pur_cd" in oc and "86" in oc and "mojarra.ab" in oc:
            fitness_anchor_id = a.get("id")
            break

    if not fitness_anchor_id:
        m_a = re.search(r'id=["\'](j_idt\d+)["\'][^>]*onclick=["\'][^"\']*pur_cd[\'"]:\s*[\'"]86[\'"]', r5.text)
        if m_a:
            fitness_anchor_id = m_a.group(1)

    if not fitness_anchor_id:
        raise RuntimeError("Could not locate fitness purpose (pur_cd=86) anchor.")

    login_form = soup5.find("form", id="loginForm")
    form_data = {}
    if login_form:
        for inp in login_form.find_all("input"):
            iname = inp.get("name")
            ival = inp.get("value", "")
            if iname:
                form_data[iname] = ival

    form_data.update({
        "loginForm": "loginForm",
        "tabs": "on",
        "InputEnter": "",
        "javax.faces.source": fitness_anchor_id,
        "javax.faces.partial.event": "click",
        "javax.faces.partial.execute": f"{fitness_anchor_id} {fitness_anchor_id}",
        "pur_cd": "86",
        "javax.faces.behavior.event": "action",
        "javax.faces.partial.ajax": "true",
        "javax.faces.ViewState": vs,
    })

    try:
        r6 = session.post(
            f"{BASE_URL}/vahanservice/vahan/ui/usermgmt/login.xhtml",
            headers={
                "Faces-Request": "partial/ajax",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Referer": full_redir_1,
            },
            data=form_data,
            timeout=30
        )
        redir_url_2 = mikasa_extract_redirect_url(r6.text)
        if not redir_url_2:
            raise RuntimeError("Expected redirect to fitness form")
        full_fitness_url = urllib.parse.urljoin(BASE_URL, redir_url_2)
    except Exception as e:
        raise RuntimeError(f"Fitness selection failed: {str(e)}")

    try:
        r7 = session.get(full_fitness_url, headers={"Referer": full_redir_1}, timeout=30)
        if r7.status_code != 200:
            raise RuntimeError(f"Fitness form failed: status {r7.status_code}")
    except Exception as e:
        raise RuntimeError(f"Fitness form error: {str(e)}")

    vs = levi_extract_viewstate(r7.text)

    data_validate = {
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": "balanceFeesFine:validate_dtls",
        "javax.faces.partial.execute": "@all",
        "javax.faces.partial.render": "balanceFeesFine:auth_panel",
        "balanceFeesFine:validate_dtls": "balanceFeesFine:validate_dtls",
        "balanceFeesFine": "balanceFeesFine",
        "balanceFeesFine:tf_chasis_no": clean_chassis_no,
        "javax.faces.ViewState": vs,
    }

    try:
        r8 = session.post(
            full_fitness_url,
            headers={
                "Faces-Request": "partial/ajax",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Referer": full_fitness_url,
            },
            data=data_validate,
            timeout=30
        )
    except Exception as e:
        raise RuntimeError(f"Chassis validation failed: {str(e)}")

    mobile_match = re.search(r'id=["\']balanceFeesFine:tf_mobile["\'][^>]*value=["\']([^"\']*)["\']', r8.text)
    if not mobile_match:
        mobile_match = re.search(r'name=["\']balanceFeesFine:tf_mobile["\'][^>]*value=["\']([^"\']*)["\']', r8.text)

    if mobile_match and mobile_match.group(1).strip():
        return mobile_match.group(1).strip()

    err_match = re.search(r'class=["\'][^"\']*ui-messages-error-detail[^"\']*["\'][^>]*>([^<]+)<', r8.text)
    if err_match:
        raise RuntimeError(f"Parivahan Error: {err_match.group(1).strip()}")

    raise RuntimeError("Mobile number could not be found.")

def ymir_get_vehicle_details(vehicle_no):
    vehicle_no = vehicle_no.upper().replace(" ", "")
    session = create_session_with_retries()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Origin": "https://www.smcinsurance.com",
        "Referer": "https://www.smcinsurance.com/",
    })
    try:
        session.get("https://www.smcinsurance.com/", timeout=15)
        time.sleep(1)
        payload = {"URL": "GetVaahanDetailsByVehicleNo", "Props": [vehicle_no], "Token": ""}
        headers = {
            "Content-Type": "application/json",
            "Origin": "https://www.smcinsurance.com",
            "Referer": "https://www.smcinsurance.com/",
        }
        response = session.post(
            "https://www.smcinsurance.com/central/centralcall/CallReqWithHeader",
            json=payload,
            headers=headers,
            timeout=15
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise RuntimeError(f"Vehicle details API error: {str(e)}")

app = Flask(__name__)


def _error(message, status):
    return jsonify({"error": message}), status


@app.get("/")
def vehicle_lookup():
    raw_vehicle_no = request.args.get("rc", "")
    vehicle_no = re.sub(r"\s+", "", raw_vehicle_no).upper()

    if not vehicle_no:
        return _error("Missing required query parameter: rc", 400)
    if not re.fullmatch(r"[A-Z0-9-]{4,15}", vehicle_no):
        return _error("Invalid vehicle registration number", 400)

    try:
        vehicle_data = ymir_get_vehicle_details(vehicle_no)
    except Exception as exc:
        return _error(f"Vehicle details lookup failed: {exc}", 502)

    if not isinstance(vehicle_data, dict) or vehicle_data.get("statusCode") != 200:
        return _error("Vehicle not found or upstream lookup failed", 404)

    response_data = vehicle_data.get("response")
    if not isinstance(response_data, dict):
        return _error("Vehicle response is missing or invalid", 502)

    chassis = response_data.get("chassis")
    if not chassis:
        return _error("Chassis number not found in vehicle data", 404)

    result = dict(vehicle_data)
    result["vehicleNumber"] = vehicle_no

    try:
        result["mobile"] = hange_fetch_mobile(vehicle_no, str(chassis))
        result["mobileLookupStatus"] = "success"
    except Exception as exc:
        # Parivahan may reset requests from serverless/cloud IPs. Still return
        # the complete vehicle response instead of discarding usable data.
        result["mobile"] = None
        result["mobileLookupStatus"] = "unavailable"
        result["mobileLookupError"] = str(exc)

    return jsonify(result)


''' Legacy CLI implementation retained below for reference only.

def historia_main():
    console.print(Panel.fit("[bold cyan]Vehicle Information System[/bold cyan]", border_style="cyan"))
    
    while True:
        vehicle_no = console.input("\n[bold yellow]Enter Vehicle Number: [/bold yellow]").strip().upper()
        if not vehicle_no:
            console.print("[red]Vehicle number cannot be empty.[/red]")
            continue

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task1 = progress.add_task("[cyan]Fetching vehicle details...", total=None)
            try:
                vehicle_data = ymir_get_vehicle_details(vehicle_no)
                progress.update(task1, completed=True)
            except Exception as e:
                console.print(f"[red]Failed to fetch vehicle details: {e}[/red]")
                continue

        if vehicle_data.get("statusCode") != 200:
            console.print("[red]Failed to retrieve vehicle information.[/red]")
            continue

        response_data = vehicle_data.get("response", {})
        chassis_full = response_data.get("chassis", "")
        if not chassis_full:
            console.print("[red]Chassis number not found in vehicle data.[/red]")
            continue

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task2 = progress.add_task("[cyan]Fetching registered mobile number...", total=None)
            try:
                mobile_number = hange_fetch_mobile(vehicle_no, chassis_full)
                progress.update(task2, completed=True)
            except Exception as e:
                console.print(f"[red]Failed to fetch mobile number: {e}[/red]")
                continue

        table = Table(title=f"Vehicle Details - {vehicle_no}", title_style="bold cyan", border_style="cyan")
        table.add_column("Field", style="bold yellow")
        table.add_column("Value", style="white")

        fields = [
            ("Registration Number", response_data.get("regNo", "N/A")),
            ("Chassis Number", response_data.get("chassis", "N/A")),
            ("Engine Number", response_data.get("engine", "N/A")),
            ("Registration Date", response_data.get("regDate", "N/A")),
            ("Vehicle Class", response_data.get("vehicleClass", "N/A")),
            ("Manufacturer", response_data.get("manufacturer", "N/A")),
            ("Vehicle Model", response_data.get("vehicle", "N/A")),
            ("Variant", response_data.get("variant", "N/A")),
            ("Fuel Type", response_data.get("fuelType", "N/A")),
            ("Cubic Capacity", str(response_data.get("cubicCapacity", "N/A"))),
            ("Owner Name", response_data.get("owner", "N/A")),
            ("Owner Father", response_data.get("ownerFatherName", "N/A")),
            ("Insurance Company", response_data.get("insuranceCompanyName", "N/A")),
            ("Insurance Valid Upto", response_data.get("insuranceUpto", "N/A")),
            ("PUCC Valid Upto", response_data.get("puccValidUpto", "N/A")),
            ("RTO", response_data.get("rtoCode", "N/A")),
            ("RTO Name", response_data.get("rtoName", "N/A")),
            ("Financer", response_data.get("financerName", "N/A")),
            ("Address", response_data.get("presentAddress", "N/A")),
            ("Pincode", response_data.get("pincode", "N/A")),
            ("Registered Mobile", mobile_number),
        ]

        for field, value in fields:
            table.add_row(field, str(value) if value else "N/A")

        console.print()
        console.print(table)
        console.print()

        output_data = {
            "vehicle": vehicle_no,
            "chassis": response_data.get("chassis", "N/A"),
            "engine": response_data.get("engine", "N/A"),
            "registration_date": response_data.get("regDate", "N/A"),
            "vehicle_class": response_data.get("vehicleClass", "N/A"),
            "manufacturer": response_data.get("manufacturer", "N/A"),
            "model": response_data.get("vehicle", "N/A"),
            "variant": response_data.get("variant", "N/A"),
            "fuel_type": response_data.get("fuelType", "N/A"),
            "cc": response_data.get("cubicCapacity", "N/A"),
            "owner": response_data.get("owner", "N/A"),
            "owner_father": response_data.get("ownerFatherName", "N/A"),
            "insurance_company": response_data.get("insuranceCompanyName", "N/A"),
            "insurance_upto": response_data.get("insuranceUpto", "N/A"),
            "pucc_valid_upto": response_data.get("puccValidUpto", "N/A"),
            "rto": response_data.get("rtoCode", "N/A"),
            "rto_name": response_data.get("rtoName", "N/A"),
            "financer": response_data.get("financerName", "N/A"),
            "address": response_data.get("presentAddress", "N/A"),
            "pincode": response_data.get("pincode", "N/A"),
            "mobile": mobile_number,
        }

        console.print(Panel(json.dumps(output_data, indent=2, ensure_ascii=False), title="[bold green]JSON Output[/bold green]", border_style="green"))

        again = console.input("\n[bold yellow]Search another vehicle? (y/n): [/bold yellow]").strip().lower()
        if again != "y":
            break

    console.print("\n[bold green]Goodbye![/bold green]")

'''

if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5000")),
        debug=False,
    )
