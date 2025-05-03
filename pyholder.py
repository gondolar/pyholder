import os, sys, inspect;

def get_this_filename() -> str : return inspect.getfile(lambda: None).replace('\\', "/");
sys.path.insert(0, "/".join(os.path.dirname(get_this_filename()).split('/')[:-1]));  # Add the parent directory to sys.path

from phyton import pathForDataSource, pathForCodeSource, filenameForDataPyTime, filenameForCodePyTime, fileList, pathForFileTarget, etsPathValidate, pathPartsTrimmed;
from yce_ping import read_packet_hex;

import json, time, io;
from typing import Any;
from fastapi import FastAPI, BackgroundTasks, Request;
from fastapi.responses import JSONResponse, StreamingResponse;

def respond_json(http_code: int, dict_response: dict ) -> int                 : print(f"Response: {http_code} ->", dict_response); return JSONResponse(content=dict_response, status_code=http_code)  
def respond_file(http_code: int, byte_response: bytes) -> StreamingResponse   : print(f"Response: {http_code} ->", byte_response); return StreamingResponse(io.BytesIO(byte_response), media_type="application/octet-stream", status_code=http_code)

def respond_settings_update(mac_address: str, received_settings_str: str, file_name: str):
    post_data_json      : dict  = json.loads(received_settings_str);
    update_soc_clock : bool  = False; 
    if(file_name.startswith("active_")):
        if(file_name.startswith("active_settings.") and "last_server_time" in post_data_json and post_data_json["last_server_time"] < post_data_json["TNO_VERSION_TIME"]):
            update_soc_clock = True;
        file_name = file_name.replace("active_", "");
    elif(file_name.startswith("fs_")):
        file_name = file_name.replace("fs_", "active_");
    settings_merged     : dict  = {};
    settings_filename   : str   = file_name + ".json";
    mac_addr_path       : str   = "/".join([pathForDataSource(mac_address), settings_filename]);
    settings_path       : str   = mac_addr_path if os.path.exists(mac_addr_path) else "/".join([pathForDataSource(), settings_filename]);
    if not os.path.exists(settings_path):
        print("'%s' settings update file not found." % settings_path);
    else:
        print("Settings update file found: '%s'." % settings_path);
        post_json_sections  : list  = [sectionKey for sectionKey in post_data_json.keys() if type(post_data_json[sectionKey]) == type({})]; print("post_json_sections:", post_json_sections);
        post_json_flat      : dict  = {};
        for sectionKey in post_json_sections:
            sectionDict         : dict  = post_data_json[sectionKey];
            for k in sectionDict:
                post_json_flat[k] = sectionDict[k];
        #print("post_json_flat:", post_json_flat);
        with open(settings_path, "r") as settings_file:
            settings_dict       : dict  = json.loads(settings_file.read());
            settings_to_merge   : list  = [k for k in settings_dict if k not in post_json_flat or settings_dict[k] != post_json_flat[k]];
            for k in settings_to_merge:
                if k not in ["TNO_VERSION_FILENAME", "TNO_VERSION_COMMIT", "TNO_VERSION_HOUR", "TNO_VERSION_MINUTE", "TNO_VERSION_STRING", "TNO_VERSION_TIME"]:
                    settings_merged[k]  = settings_dict[k];
    if update_soc_clock:
        settings_merged["last_server_time"] = int(time.time());

    return respond_json(200, settings_merged);

def get_firmware_update_bytes(mac_address: str, settings_string: str):
    firmware_folder : str   = pathForCodeSource(mac_address);
    if os.path.exists(firmware_folder):
        firmware_files  : list  = list_files(firmware_folder, ".bin", False);
        settings_dict   : dict  = json.loads(settings_string);
        rollback_from   : str   = settings_dict["rollback_from"] if ("rollback_from" in settings_dict) else filenameForCodePyTime(0);
        if(rollback_from in firmware_files):
            firmware_files.remove(rollback_from);
        if(len(firmware_files)):
            last_firmware   : str   = firmware_files[-1];
            has_build_info  : bool  = "TNO_VERSION_FILENAME" in settings_dict;
            soc_firmware    : str   = settings_dict["TNO_VERSION_FILENAME"] if (has_build_info and -1 == settings_dict["TNO_SETTINGS_SOURCE"].find(".mini.")) else filenameForCodePyTime(0);
            last_is_newer   : bool  = soc_firmware != sorted([last_firmware, soc_firmware])[1];
            if last_is_newer:
                with open('/'.join([firmware_folder, last_firmware]), "rb") as firmware_file:
                    print("Firmware update available: '%s'" % last_firmware);
                    return firmware_file.read();
    print("No firmware update available.");
    return bytes();

def respond_firmware_update(mac_address: str, settings_string: str):
    firmware_bytes  : bytes = get_firmware_update_bytes(mac_address, settings_string);
    return respond_file(200, firmware_bytes) if len(firmware_bytes) else respond_json(200, {});

def respond_ping(mac_address: str, ping_string: str):
    requestBody     : dict[str, Any]    = json.loads(ping_string)
    latitude        : float = requestBody["iridium_latitude" ] if "iridium_latitude"  in requestBody else requestBody["latitude" ] if "latitude"  in requestBody else 0;
    longitude       : float = requestBody["iridium_longitude"] if "iridium_longitude" in requestBody else requestBody["longitude"] if "longitude" in requestBody else 0;
    transmit_time   : str   = requestBody["transmit_time"];
    hexencoded      : str   = requestBody["data"];
    packet_header, packet_sections, packet_bytes = read_packet_hex(hexencoded);

    print("Latitude          :", latitude )
    print("Longitude         :", longitude)
    print("Transmission time :", transmit_time)
    print("Packet header     :", packet_header)

    if(packet_sections):
        print("Packet sections:", packet_sections)

    if(packet_bytes):
        errmsg  : str   = str(len(packet_bytes)) + " bytes not parsed! '" + str(packet_bytes) + "'";
        print(errmsg);
        return respond_json(self, 403, errmsg);
    
    return respond_json(self, 200, {"message":"ok"});   # do backend job here

def calc_settings_diff(json_historic_settings: dict, json_received_data: dict) -> tuple[dict, dict]:
    keys_to_delete          : list  = [];
    json_received_settings  : dict  = {};
    for k in json_historic_settings:
        if not (k in json_received_data):
            continue;
        if(json_received_data[k] == json_historic_settings[k]):
            keys_to_delete.append(k); #print("Removed setting with no changes:", k);
        else:
            json_received_settings[k] = json_received_data[k];

    for k in keys_to_delete:
        del json_historic_settings[k];

    return (json_historic_settings, json_received_settings);

def save_settings_diff(timeless_settings: bytes, received_data: bytes, target_folder: str, file_name: str, file_extension: str):
    if("active_state" == file_name):
        return;
    try:
        json_historic_settings  : dict  = json.loads(timeless_settings.decode("utf-8"));
    except:
        print("invalid json in server:", file_name, timeless_settings);
    try:
        json_received_data      : dict  = json.loads(received_data.decode("utf-8"));
    except:
        print("invalid json received:", file_name, received_data);
    json_historic_settings, json_received_settings  = calc_settings_diff(json_historic_settings, json_received_data);
    print("Previous values  :", json_historic_settings, "\nUpdated keys     :", json_received_settings);
    historic_filename  = filenameForDataFromPyTime(time.time(), file_name, file_extension);
    historic_filepath  = "/".join([target_folder, historic_filename]);
    print("Settings diff saved to '%s'." % historic_filepath);
    with open(historic_filepath, mode="wb") as settings_file:
        settings_file.write(json.dumps(json_historic_settings).encode('utf-8'));

def save_received_file(received_data: bytes, target_folder: str, file_name: str, file_extension: str):
    if   ("settings" == file_name): file_name = "fs_" + file_name;
    elif ("settings_sleep" == file_name): file_name = "fs_" + file_name;
    timeless_filename   = ".".join([file_name, file_extension]);
    timeless_filepath   = "/".join([target_folder, timeless_filename]);
    if not os.path.exists(target_folder):
        os.makedirs(target_folder);
    elif file_extension == "json" and os.path.exists(timeless_filepath):
        timeless_settings       : bytes = bytes();
        with open(timeless_filepath, "rb") as f:
            timeless_settings   = f.read();
        if(timeless_settings == received_data):
            print("Data has no changes. Skipping save...");
            return;
        save_settings_diff(timeless_settings, received_data, target_folder, file_name, file_extension);

    with open(timeless_filepath, mode="wb") as settings_file:
        settings_file.write(received_data);

app = FastAPI();

@app.post("/{mac_address}/{received_filename}.json")
async def process(request: Request, mac_address: str, received_filename: str, background_tasks: BackgroundTasks): #, postbody: str = Body(..., embed=True)):
    print("mac_address:'" + mac_address + "'. received_filename:'" + received_filename + "'");
    #filename_parts      : str = path_trimmed_parts(received_filename, ".");
    #if(2 > len(filename_parts)): # expected `[file_name, file_extension]`
    #    return respond_json(403, {"message": "invalid filename: " + received_filename});
    post_body           : bytes = await request.body();     print("post_body:", post_body.decode());
    file_name           : str   = received_filename;                    #'.'.join(filename_parts[:-1]);
    file_extension      : str   = "json";                           #filename_parts[-1].lower();
    path_settings       : bytes = pathForFileTarget(".".join([received_filename, file_extension]), mac_address);
    save_received_file(post_body, path_settings, file_name, file_extension);

    post_body_str   : str   = json.dumps(json.loads(post_body.decode("utf-8"))); print("post_body_str:", post_body_str);
    if(file_name.replace("fs_", "") in ["active_settings", "settings", "settings_sleep"]):
        return respond_settings_update(mac_address, post_body_str, file_name);
    elif("active_state" == file_name):
        return respond_firmware_update(mac_address, post_body_str);
    elif("ping" == file_name):
        return respond_ping(mac_address, post_body_str);

    return respond_json(403, {"message": "invalid name: '%s'" % received_filename}); 
