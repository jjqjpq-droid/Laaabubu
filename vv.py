#!/usr/bin/env python3

import os
import random
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

# Optional single trusted proxy, provided via env var. Takes priority over
# the fallback public pool below. Format: "http://user:pass@host:port" or
# "socks5://host:port".
PARIVAHAN_PROXY_URL = os.environ.get("PARIVAHAN_PROXY_URL", "").strip()

# Fallback pool of public SOCKS4 proxies. These are unauthenticated,
# third-party proxies with no uptime guarantee — most entries are dead at
# any given time, and none of them should be trusted with sensitive traffic
# in production. They exist only as a best-effort way to route around
# Parivahan blocking outbound cloud/datacenter IPs. Prefer setting
# PARIVAHAN_PROXY_URL to a trusted paid proxy instead of relying on this list.
_PUBLIC_PROXY_POOL = [
    "72.195.34.59:4145", "221.226.188.218:10800", "72.195.34.41:4145",
    "72.195.101.99:4145", "72.195.34.42:4145", "198.8.94.170:4145",
    "72.195.34.58:4145", "192.252.220.92:17328", "202.69.38.42:5678",
    "72.195.114.184:4145", "143.255.140.28:5678", "72.195.114.169:4145",
    "192.252.208.67:14287", "196.29.231.1:4145", "72.37.216.68:4145",
    "200.41.182.243:4145", "110.238.111.229:8999", "192.252.208.70:14282",
    "192.111.130.2:4145", "104.37.135.145:4145", "192.252.211.197:14921",
    "72.37.217.3:4145", "98.170.57.231:4145", "186.190.228.83:4153",
    "199.58.184.97:4145", "199.187.210.54:4145", "98.188.47.150:4145",
    "199.116.114.11:4145", "69.61.200.104:36181", "177.85.65.177:4153",
    "192.252.216.81:4145", "129.205.244.158:1080", "74.119.147.209:4145",
    "162.255.108.249:5678", "213.7.196.26:4153", "98.170.57.249:4145",
    "98.188.47.132:4145", "184.181.217.210:4145", "184.181.217.220:4145",
    "184.181.217.194:4145", "91.150.189.122:60647", "142.54.232.6:4145",
    "103.144.209.104:3629", "110.238.109.146:8060", "192.111.137.34:18765",
    "200.105.192.6:5678", "192.111.137.37:18762", "184.181.217.213:4145",
    "201.174.239.28:4153", "121.200.60.122:4153", "184.181.217.206:4145",
    "122.248.46.26:4145", "74.119.144.60:4145", "203.160.58.194:4145",
    "110.238.109.146:8080", "125.227.169.85:38157", "81.16.9.222:3629",
    "181.15.154.154:52033", "104.200.135.46:4145", "174.77.111.196:4145",
    "142.54.239.1:4145", "184.181.217.201:4145", "193.158.12.138:4153",
    "208.102.51.6:58208", "174.77.111.197:4145", "67.201.33.10:25283",
    "64.124.145.1:1080", "38.83.108.89:5678", "142.54.229.249:4145",
    "199.102.104.70:4145", "107.152.98.5:4145", "200.125.40.38:5678",
    "108.175.24.1:13135", "68.71.254.6:4145", "192.252.214.20:15864",
    "184.178.172.14:4145", "192.111.135.18:18301", "192.111.135.17:18302",
    "70.166.167.38:57728", "199.102.106.94:4145", "184.178.172.13:15311",
    "184.178.172.26:4145", "142.54.226.214:4145", "200.123.109.166:4153",
    "101.109.245.200:4153", "174.77.111.198:49547", "142.54.237.34:4145",
    "192.111.130.5:17002", "184.178.172.17:4145", "98.178.72.21:10919",
    "174.75.211.222:4145", "72.214.108.67:4145", "184.178.172.28:15294",
    "184.178.172.25:15291", "14.161.17.4:4153", "184.170.245.148:4145",
    "82.132.19.108:4153", "142.54.235.9:4145", "184.178.172.3:4145",
    "103.17.90.6:5678", "195.78.100.162:3629", "184.178.172.23:4145",
    "192.252.215.5:16137", "104.200.152.30:4145", "184.178.172.11:4145",
    "192.111.137.35:4145", "122.146.95.183:4145", "184.178.172.5:15303",
    "199.58.185.9:4145", "103.121.214.50:4145", "24.249.199.4:4145",
    "192.111.134.10:4145", "142.54.231.38:4145", "107.181.168.145:4145",
    "98.181.137.83:4145", "192.111.138.29:4145", "24.249.199.12:4145",
    "184.170.248.5:4145", "72.195.34.60:27391", "174.64.199.82:4145",
    "66.42.224.229:41679", "142.54.236.97:4145", "192.111.139.163:19404",
    "192.111.129.145:16894", "198.8.84.3:4145", "185.215.53.129:3629",
    "199.102.105.242:4145", "174.64.199.79:4145", "98.181.137.80:4145",
    "68.71.249.153:48606", "188.143.169.22:33333", "192.111.139.162:4145",
    "187.19.127.246:8011", "142.54.228.193:4145", "110.238.111.229:6789",
    "199.102.107.145:4145", "123.57.1.78:3128", "199.229.254.129:4145",
    "103.225.125.161:4153", "170.81.141.49:61437", "103.140.35.11:4145",
    "198.8.94.174:39078", "68.71.247.130:4145", "205.177.85.130:39593",
    "206.220.175.2:4145", "68.1.210.189:4145", "187.44.211.118:4153",
    "192.111.139.165:4145", "162.253.68.97:4145", "107.181.161.81:4145",
    "91.150.77.58:56921", "183.88.240.139:4153", "98.175.31.195:4145",
    "192.252.220.89:4145", "82.130.202.219:43429", "184.170.249.65:4145",
    "68.1.210.163:4145", "184.178.172.18:15280", "109.224.22.36:51372",
]

# How many proxies from the pool to try (in random order) before giving up
# and falling back to a direct connection. Kept small so a mostly-dead list
# doesn't add minutes of latency to every request.
_PROXY_ATTEMPT_LIMIT = 8
_PROXY_CONNECT_TIMEOUT = 6


def _candidate_proxy_urls():
    """Yield proxy URLs to try, in priority order."""
    if PARIVAHAN_PROXY_URL:
        yield PARIVAHAN_PROXY_URL
    pool = list(_PUBLIC_PROXY_POOL)
    random.shuffle(pool)
    for host_port in pool[:_PROXY_ATTEMPT_LIMIT]:
        # These are SOCKS4 proxies; requests needs PySocks (requests[socks])
        # installed to use the socks4:// scheme.
        yield f"socks4://{host_port}"


def create_session_with_retries(proxy_url=None):
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
    if proxy_url:
        session.proxies.update({"http": proxy_url, "https": proxy_url})
    return session


def create_parivahan_session():
    """
    Build a session for talking to the Parivahan portal, trying a proxy pool
    first (since Parivahan resets connections from most cloud/datacenter
    IPs) and falling back to a direct connection if none of the proxies work.
    Returns (session, proxy_used_or_None).
    """
    for proxy_url in _candidate_proxy_urls():
        candidate = create_session_with_retries(proxy_url)
        try:
            probe = candidate.get(
                HOMEPAGE_URL, timeout=_PROXY_CONNECT_TIMEOUT
            )
            if probe.status_code == 200:
                return candidate, proxy_url
        except Exception:
            continue
    # No working proxy found (or none configured) — fall back to direct.
    return create_session_with_retries(), None

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

    session, proxy_used = create_parivahan_session()
    session.headers.update(COMMON_HEADERS)

    try:
        r1 = session.get(HOMEPAGE_URL, timeout=30)
        if r1.status_code != 200:
            raise RuntimeError(f"Failed to access Parivahan portal: status {r1.status_code}")
    except Exception as e:
        detail = f" (via proxy {proxy_used})" if proxy_used else " (direct, no proxy)"
        raise RuntimeError(f"Connection error{detail}: {str(e)}")

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

    # Build the FULL raw payload returned by the Parivahan validation step,
    # not just the mobile number. Every input/textarea rendered inside the
    # AJAX update fragments (auth panel, balanceFeesFine form fields, any
    # embedded messages) is captured as-is so callers get the complete
    # second-source response rather than a single extracted field.
    full_source_data = {}
    try:
        root8 = ET.fromstring(r8.text)
        for upd in root8.findall(".//update"):
            update_id = upd.get("id", "")
            update_html = upd.text or ""
            frag_soup = BeautifulSoup(update_html, "html.parser")
            frag_fields = {}
            for inp in frag_soup.find_all(["input", "textarea", "select"]):
                iname = inp.get("name") or inp.get("id")
                if not iname:
                    continue
                if inp.name == "select":
                    selected = inp.find("option", selected=True)
                    ival = selected.get("value", "") if selected else ""
                elif inp.name == "textarea":
                    ival = inp.text or ""
                else:
                    ival = inp.get("value", "")
                frag_fields[iname] = ival
            for msg in frag_soup.select(".ui-messages-error-detail, .ui-message-error-detail"):
                frag_fields.setdefault("_messages", []).append(msg.get_text(strip=True))
            if frag_fields:
                full_source_data[update_id or f"fragment_{len(full_source_data)}"] = frag_fields
    except Exception:
        pass

    if not full_source_data:
        all_fields = {}
        for inp in BeautifulSoup(r8.text, "html.parser").find_all(["input", "textarea", "select"]):
            iname = inp.get("name") or inp.get("id")
            if not iname:
                continue
            if inp.name == "select":
                selected = inp.find("option", selected=True)
                ival = selected.get("value", "") if selected else ""
            elif inp.name == "textarea":
                ival = inp.text or ""
            else:
                ival = inp.get("value", "")
            all_fields[iname] = ival
        full_source_data["raw"] = all_fields

    mobile_value = None
    for frag in full_source_data.values():
        if isinstance(frag, dict):
            for key, val in frag.items():
                if key.endswith("tf_mobile") and str(val).strip():
                    mobile_value = str(val).strip()
                    break
        if mobile_value:
            break

    if not mobile_value:
        err_match = re.search(r'class=["\'][^"\']*ui-messages-error-detail[^"\']*["\'][^>]*>([^<]+)<', r8.text)
        if err_match:
            raise RuntimeError(f"Parivahan Error: {err_match.group(1).strip()}")
        raise RuntimeError("Mobile number could not be found.")

    return {"mobile": mobile_value, "raw": full_source_data}

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
        mobile_result = hange_fetch_mobile(vehicle_no, str(chassis))
        result["mobile"] = mobile_result["mobile"]
        result["mobileSourceRawResponse"] = mobile_result["raw"]
        result["mobileLookupStatus"] = "success"
    except Exception as exc:
        # Parivahan may reset requests from serverless/cloud IPs. Still return
        # the complete vehicle response instead of discarding usable data.
        result["mobile"] = None
        result["mobileSourceRawResponse"] = None
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
