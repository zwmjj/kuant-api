"""Download API — serves release packages, individual packages, and reports."""
import os, json
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

BASE = os.path.join(os.path.dirname(__file__), '..', '..')
RELEASE_DIR = os.path.join(BASE, 'releases')
PKG_DIR = os.path.join(RELEASE_DIR, 'packages')


@router.get("/manifest")
async def get_manifest():
    path = os.path.join(RELEASE_DIR, "manifest.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"error": "No release available"}


@router.get("/package")
async def download_full_package():
    path = os.path.join(RELEASE_DIR, "manifest.json")
    if not os.path.exists(path):
        return {"error": "No release"}
    with open(path) as f:
        manifest = json.load(f)
    zip_path = os.path.join(RELEASE_DIR, manifest["zip"])
    if os.path.exists(zip_path):
        return FileResponse(zip_path, filename=manifest["zip"], media_type="application/zip")
    return {"error": "Package not found"}


@router.get("/catalog")
async def get_catalog():
    """Get catalog of all individual packages."""
    path = os.path.join(PKG_DIR, "catalog.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"packages": [], "total": 0}


@router.get("/item/{item_id}")
async def download_item(item_id: str):
    """Download individual factor/strategy/research/feature package."""
    zip_path = os.path.join(PKG_DIR, f"{item_id}.zip")
    if os.path.exists(zip_path):
        return FileResponse(zip_path, filename=f"{item_id}.zip", media_type="application/zip")
    return {"error": f"Package not found: {item_id}"}


@router.get("/whitepaper")
async def download_whitepaper():
    for name in ["reports/whitepaper.md", "AUDIT_REPORT.md"]:
        path = os.path.join(BASE, name)
        if os.path.exists(path):
            return FileResponse(path, filename="Kuant_WhitePaper.md", media_type="text/markdown")
    return {"error": "Not found"}


@router.get("/readme")
async def download_readme():
    path = os.path.join(BASE, "README.md")
    if os.path.exists(path):
        return FileResponse(path, filename="README.md", media_type="text/markdown")
    return {"error": "Not found"}


@router.get("/data-sources")
async def download_data_sources():
    path = os.path.join(BASE, "DATA_SOURCES.md")
    if os.path.exists(path):
        return FileResponse(path, filename="DATA_SOURCES.md", media_type="text/markdown")
    return {"error": "Not found"}


@router.get("/list")
async def list_downloads():
    """List all available downloads (full package + reports + individual items)."""
    files = []

    # Full package
    manifest_path = os.path.join(RELEASE_DIR, "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            m = json.load(f)
        zip_path = os.path.join(RELEASE_DIR, m.get("zip", ""))
        if os.path.exists(zip_path):
            files.append({
                "name": m["zip"], "label": f"Full Source v{m['version']}",
                "description": f"{m['files']} files, complete platform",
                "size": os.path.getsize(zip_path), "type": "package",
                "endpoint": "package",
            })

    # Reports
    for name, label, desc, endpoint in [
        ("AUDIT_REPORT.md", "White Paper", "Full audit report + methodology + results", "whitepaper"),
        ("README.md", "README", "Project documentation", "readme"),
        ("DATA_SOURCES.md", "Data Sources", "Free and paid data source guide", "data-sources"),
    ]:
        path = os.path.join(BASE, name)
        if os.path.exists(path):
            files.append({"name": name, "label": label, "description": desc,
                          "size": os.path.getsize(path), "type": "report", "endpoint": endpoint})

    # Individual packages from catalog
    catalog_path = os.path.join(PKG_DIR, "catalog.json")
    if os.path.exists(catalog_path):
        with open(catalog_path) as f:
            cat = json.load(f)
        for pkg in cat.get("packages", []):
            files.append({
                "name": pkg["zip"], "label": pkg["name"],
                "description": f"{pkg['type']} — Rating: {pkg.get('rating', 'N/A')}",
                "size": pkg.get("size", 0), "type": pkg["type"],
                "endpoint": f"item/{pkg['id']}",
                "rating": pkg.get("rating"),
            })

    return {"files": files}
