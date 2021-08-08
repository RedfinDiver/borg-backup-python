#!/usr/bin/env python3

import os
import time
import subprocess
from datetime import datetime
from configparser import ConfigParser, ExtendedInterpolation
import paramiko

config = ConfigParser(allow_no_value=True, interpolation=ExtendedInterpolation())
config.read("pyborg.cfg")

excludes = ""
for exclude in config["borg"]["excludes"].splitlines():
    if exclude:
        excludes += "-e " + exclude + " "

sources = ""
for source in config["borg"]["sources"].splitlines():
    if source:
        sources += source + " "

nas_repo = config["repos"]["nas"]
nas_key = config["repos"]["nas_key"]
usb_repo = config["repos"]["usb"]
usb_key = config["repos"]["usb_key"]
name = config["user"]["name"]
user_home = config["user"]["home"]
logfile = config["user"]["logfile"]

if config.getboolean("databases", "backup"):
    db_backup = config.getboolean("databases", "backup")
    db_dir = config["databases"]["dir"]
    db_user = config["databases"]["user"]
    db_pass = config["databases"]["pwd"]

if config.getboolean("pruning", "prune"):
    prune = config.getboolean("pruning", "prune")
    rules = " "
    for rule in config["pruning"]["rules"].splitlines():
        if rule:
            rules += rule + " "

host = config["server"]["host"]
huser = config["server"]["user"]
path_cmd = config["server"]["path_cmd"]
site_cmds = {}
site_cmds["alle"] = ["alle Websites"]
site_cmds["utt"] = config["server"]["utt"].split("\n")
site_cmds["utt"].pop(0)
site_cmds["tgi"] = config["server"]["tgi"].split("\n")
site_cmds["tgi"].pop(0)
site_cmds["ooetdv"] = config["server"]["ooetdv"].split("\n")
site_cmds["ooetdv"].pop(0)
site_cmds["magcos"] = config["server"]["magcos"].split("\n")
site_cmds["magcos"].pop(0)

nas = config["syno"]["host"]
nas_user = config["syno"]["user"]
nas_path_cmd = config["syno"]["path_cmd"]


def getDatabases():
    """Get all databases on server

    This functions get all databases created by the user. It automaticall
    strips out system databases. It returns a list with the user databases.
    """
    exclude_dbs = [
        "Database",
        "mysql",
        "performance_schema",
        "information_schema",
        "sys",
        "phpmyadmin",
    ]
    dbs = []

    cmd = ["mysql", "-e", "show databases"]
    all_dbs = subprocess.run(
        cmd, stdout=subprocess.PIPE, encoding="utf-8"
    ).stdout.splitlines()

    for db in all_dbs:
        if db not in exclude_dbs:
            dbs.append(db)

    return dbs


def writeDatabases():
    """Dumps databases from server and writes the files to folder

    This function dumps databases from server and writes the .sql - files to
    a folder on the filesystem.
    """
    if not os.path.exists(db_dir):
        os.mkdir(db_dir)
    returncode = 0

    for db in getDatabases():
        path = os.path.join(db_dir, db + ".sql")
        cmd = ["mysqldump", "-u", db_user, "-p" + db_pass, db]
        result = subprocess.run(cmd, encoding="utf-8", stdout=subprocess.PIPE)

        if result.returncode > 0:
            returncode = 1

        with open(path, "w") as file:
            file.write(result.stdout)

    return returncode


def backup(repo):
    cmd = "borg create -v -s --compression lz4"

    target = (
        repo + "::" + name + "_" + datetime.now().strftime("%Y-%m-%d_%H_%M_%S") + " "
    )
    cmd += " " + target
    cmd += sources
    cmd += excludes

    result = subprocess.run(
        cmd,
        encoding="utf-8",
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    return {
        "stderr": result.stderr,
        "stdout": result.stdout,
        "returncode": result.returncode,
    }


def pruneRepo(repo, dry_run=True):
    """Prunes a repository

    This function prunes a repository as set in the configuration. With the
    parameter dry_run=True the function output what would be changed in the
    repository
    """
    cmd = "borg prune " + repo + " --list" + " --verbose"
    if dry_run:
        cmd += " --dry-run"
    cmd += rules

    result = subprocess.run(
        cmd,
        encoding="utf-8",
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    return {
        "stderr": result.stderr,
        "stdout": result.stdout,
        "returncode": result.returncode,
    }


def mountRepo(repo):
    """Mounts or unmounts a borg repository

    This function mounts or unmounts a borg repository on the filesystem. It
    is called only with the repository parameter. If the repo is already
    mounted, it is unmounted. Otherwise it is mounted.
    """
    mountpoint = os.path.join(user_home, "BORGBACKUP")

    # existing mount, unmount it
    if os.path.ismount(mountpoint):
        result_umount = subprocess.run("borg umount " + mountpoint, shell=True)
        if result_umount.returncode == 0:
            os.rmdir(mountpoint)
            if os.path.exists(mountpoint) is False:
                return ["unmount", 0]
        return ["unmount", 1]
    else:
        if not os.path.exists(mountpoint):
            os.mkdir(mountpoint)
        result_mount = subprocess.run(
            "borg mount " + repo + " " + mountpoint, shell=True
        )
        if result_mount.returncode == 0:
            return ["mount", 0]
        return ["mount", 1]


def listArchives(repo):
    """Prints all archives from a repository

    This function list all archives from a given repository.
    """
    cmd = "borg list " + repo
    result_list = subprocess.run(
        cmd, shell=True, stdout=subprocess.PIPE, encoding="utf-8"
    )

    return {"returncode": result_list.returncode, "stdout": result_list.stdout}


def info(repo):
    """Prints info of last archive

    This function prints the info of the last archive in a given borg
    repository.
    """
    cmd = "borg info " + repo + " --last 1"
    result_info = subprocess.run(
        cmd, shell=True, stdout=subprocess.PIPE, encoding="utf-8"
    )

    return {"returncode": result_info.returncode, "stdout": result_info.stdout}


def rsync_to_synology():
    """Rsyncs the websitebackups to Synology Drive

    This functions rsyncs the created zips to SynoDrive
    """
    key_file_path = os.path.join(os.environ["HOME"], ".ssh", "id_rsa")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cmd = "bash ./sync_backup.sh"
    return_object = {}

    print("Mit Server verbinden...")
    try:
        ssh.connect(nas, username=nas_user, key_filename=key_file_path)
        print(f"Verbindung mit Server {nas} hergestellt.")
    except paramiko.AuthenticationException:
        print("Verbindung mit Server {nas} gescheitert!")
        print("Bitte nochmal versuchen!")
        time.sleep(3)
        return {"returncode": 1, "stderr": "Verbindung mit Server {nas} gescheitert!"}

    stdin, stdout, stderr = ssh.exec_command(nas_path_cmd + "; " + cmd)
    if stderr.channel.exit_status > 0:
        output = stderr.readlines()
        return_object["sync"] = {
            "returncode": 1,
            "stderr": output,
            "msg": f"Fehler bei der Syncronisierung mit {nas}!",
        }
    else:
        return_object["sync"] = {
            "returncode": 0,
            "msg": f"Syncronisierung mit {nas} erfolgreich!",
        }

    ssh.close()
    return return_object
