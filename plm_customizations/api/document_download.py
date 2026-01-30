import frappe
import json
import os
import io
import zipfile
from frappe.utils.file_manager import get_file


@frappe.whitelist()
def download_item_documents(item_code, version=None):
    """
    Download documents attached to an Item as a ZIP file.
    
    Args:
        item_code: The Item code
        version: Optional version number. If None or 'current', downloads current documents.
                 Otherwise downloads from version snapshot.
    
    Files are renamed with item_code + version prefix.
    """
    # Check if download is allowed (not blocked)
    from plm_customizations.api.item_version import can_download_documents, get_version_documents
    download_check = can_download_documents(item_code)
    if isinstance(download_check, dict) and not download_check.get("can_download"):
        frappe.throw(download_check.get("reason", "Download not allowed"))
    
    # Get Item details
    item = frappe.get_doc("Item", item_code)
    item_number = item.item_code
    
    # Determine which version to download
    if version and version != "current":
        # Download from version snapshot
        version_number = f"v{version}"
        version_result = get_version_documents(item_code, version)
        if version_result.get("error"):
            frappe.throw(version_result.get("error"))
        documents = version_result.get("documents", [])
    else:
        # Download current documents
        current_version = item.get("current_version") or 1
        version_number = f"v{current_version}"
        
        # Get all Document records linked to this Item
        doc_links = frappe.get_all(
            "Item Drawing Link",
            filters={"parent": item_code, "parenttype": "Item"},
            fields=["link", "version", "type"]
        )
        
        documents = []
        for link in doc_links:
            if link.link and frappe.db.exists("Document", link.link):
                doc_record = frappe.get_doc("Document", link.link)
                documents.append({
                    "link": link.link,
                    "version": link.version,
                    "type": link.type,
                    "attachment": doc_record.get("attachment"),
                    "filename": doc_record.get("filename") or doc_record.get("attachment")
                })
    
    if not documents:
        frappe.throw("No documents found for this version")
    
    # Create folder name
    folder_name = f"{item_number}_{version_number}"
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    files_added = 0
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for doc in documents:
            attachment = doc.get("attachment")
            if not attachment:
                continue
            
            try:
                # Get file path
                if attachment.startswith("/files/"):
                    file_path = frappe.get_site_path("public", attachment.lstrip("/"))
                elif attachment.startswith("/private/files/"):
                    file_path = frappe.get_site_path(attachment.lstrip("/"))
                else:
                    # Try to get from File doctype
                    file_doc = frappe.get_doc("File", {"file_url": attachment})
                    file_path = file_doc.get_full_path()
                
                if os.path.exists(file_path):
                    # Get original filename
                    original_filename = doc.get("filename") or os.path.basename(file_path)
                    if "/" in original_filename:
                        original_filename = os.path.basename(original_filename)
                    
                    # Create new filename with prefix: {item_code}_{version}_{原文件名}
                    new_filename = f"{item_number}_{version_number}_{original_filename}"
                    
                    # Add to ZIP
                    zip_path = f"{folder_name}/{new_filename}"
                    zip_file.write(file_path, zip_path)
                    files_added += 1
                    
            except Exception as e:
                frappe.log_error(f"Error adding file {attachment}: {str(e)}")
                continue
    
    if files_added == 0:
        frappe.throw("No files could be added to the download")
    
    # Prepare response
    zip_buffer.seek(0)
    zip_filename = f"{folder_name}.zip"
    
    # Set response headers for file download
    frappe.local.response.filename = zip_filename
    frappe.local.response.filecontent = zip_buffer.getvalue()
    frappe.local.response.type = "download"


@frappe.whitelist()
def get_document_count(item_code):
    """Get count of documents for an item"""
    count = frappe.db.count("Item Drawing Link", {"parent": item_code, "parenttype": "Item"})
    return count
