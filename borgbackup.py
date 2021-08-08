#!/usr/bin/env python3

import os
import shutil
import logging
import time
import functions as cfg

text = """
=================================
    Lokales Backup mit Borg
=================================
         Backup auf NAS - [b_nas]
         Backup auf USB - [b_usb]
---------------------------------
     Mount / Umount NAS - [m_nas]
     Mount / Umount USB - [m_usb]
---------------------------------
        Archive auf NAS - [l_nas]
        Archive auf USB - [l_usb]
---------------------------------
Info letztes Backup NAS - [i_nas]
Info letztes Backup USB - [i_usb]
=================================
---------------------------------
Sync Backups nach Drive - [sync]
       Programm beenden - [x]
"""

valid_cmds = [
    "x",
    "b_nas",
    "b_usb",
    "m_nas",
    "m_usb",
    "l_nas",
    "l_usb",
    "i_nas",
    "i_usb",
]


command = ""

logging.basicConfig(
    filename=cfg.logfile,
    format="%(levelname)s:%(asctime)s:%(message)s",
    level=logging.DEBUG,
)

while True:
    os.system("clear")
    print(text)

    command = input("Wählen Sie eine Option: ")
    os.system("clear")

    # Exit the programm
    if command == "x":
        print("Das Programm wird beendet!")
        time.sleep(2)
        break

    # Backup is selected
    elif command == "b_nas" or command == "b_usb":

        print(f'Sie haben "{command}" als Ziel gewählt.')
        print()

        # Assign repo
        if command == "b_nas":
            repo = cfg.nas_repo
            os.environ["BORG_PASSPHRASE"] = cfg.nas_key
        else:
            repo = cfg.usb_repo
            os.environ["BORG_PASSPHRASE"] = cfg.usb_key

        os.environ["BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK"] = "yes"

        logging.info(f"Backup nach {repo} gestartet.")

        # Databasebackup if selected
        if cfg.db_backup:
            os.system("clear")
            print("Datenbanken werden geschrieben...")
            print()
            result_db = cfg.writeDatabases()
            print()
            if result_db == 0:
                print("Datenbanken wurden erfolgreich geschrieben!")
                logging.info("Datenbanken wurden erfolgreich geschrieben.")
            else:
                print("FEHLER: Die Datenbanken wurden NICHT erfolgreich geschrieben!")
                logging.error("Datenbanken wurden NICHT erfolgreich geschrieben")
            time.sleep(4)

        # Borgbackup
        os.system("clear")
        print("Borg wird ausgeführt...")
        print("")
        result_borg = cfg.backup(repo)
        if result_borg["returncode"] == 0:
            print("Borg hat das Backup erfolgreich beendet!")
            print("")
            print(result_borg["stderr"])
            logging.info("Borg hat den Backup erfolgreich beendet.")
            logging.info("Info zum erzeugten Archiv:\n" + result_borg["stderr"])
        else:
            print("FEHLER: Borg hat das Backup NICHT erfolgreich beendet!")
            print("")
            print(result_borg["stderr"])
            logging.error("Borg hat den Backup NICHT erfolgreich beendet!")
            logging.error(result_borg["stderr"])

        shutil.rmtree(cfg.db_dir)  # remove database directory after backup
        time.sleep(4)

        # Pruning the repo if selected
        if cfg.prune:
            os.system("clear")
            print("Pruning des Repos wird vorbereitet...")
            print("")
            msg_dry = cfg.pruneRepo(repo, dry_run=True)
            print(msg_dry["stderr"])
            print("")
            select = input(
                f"Wollen Sie die Änderungen am {repo} durchführen? (Ja/NEIN): "
            )
            if select == "Ja" or select == "JA" or select == "1":
                msg = cfg.pruneRepo(repo, dry_run=False)
                print(msg["stderr"])
                print("")
                print("Repo wurde geändert!")
                logging.info("Repo Pruning wurde durchgeführt.")
                logging.info("Information zum Pruning:\n" + msg["stderr"])
            else:
                print("")
                print("Repo wurde NICHT geändert!")
                logging.info(
                    "Repo Pruning wurde nicht durchgeführt. Keine Daten geändert"
                )
        time.sleep(4)

    # Mounting is selected
    elif command == "m_nas" or command == "m_usb":

        # Assign repo
        if command == "m_nas":
            repo = cfg.nas_repo
            os.environ["BORG_PASSPHRASE"] = cfg.nas_key
        else:
            repo = cfg.usb_repo
            os.environ["BORG_PASSPHRASE"] = cfg.usb_key

        os.system("clear")
        print(f'Das Repo "{repo}" wird mounted/unmounted...')
        print()
        result_mount = cfg.mountRepo(repo)
        if result_mount[0] == "mount" and result_mount[1] == 1:
            print(f"FEHLER: Das Mounten des Repo {repo} in ist gescheitert!")
        elif result_mount[0] == "mount" and result_mount[1] == 0:
            print(f"Das Mounten des Repo {repo} war erfolgreich.")
        elif result_mount[0] == "unmount" and result_mount[1] == 1:
            print(f"FEHLER: Das Unmounten des Repo {repo} ist gescheitert!")
        elif result_mount[0] == "unmount" and result_mount[1] == 0:
            print(f"Das Unmounten des Repo {repo} war erfolgreich.")
        time.sleep(4)

    # List archives in repo
    elif command == "l_nas" or command == "l_usb":

        # Assign repo
        if command == "l_nas":
            repo = cfg.nas_repo
            os.environ["BORG_PASSPHRASE"] = cfg.nas_key
        else:
            repo = cfg.usb_repo
            os.environ["BORG_PASSPHRASE"] = cfg.usb_key

        os.system("clear")
        print(f"Die Archive im {repo} werden aufgelistet...")
        print()
        print(cfg.listArchives(repo)["stdout"])
        print()
        input("Drücken Sie eine beliebige Taste um fortzufahren.")

    # Info of last archive in repo
    elif command == "i_nas" or command == "i_usb":

        # Assign repo
        if command == "i_nas":
            repo = cfg.nas_repo
            os.environ["BORG_PASSPHRASE"] = cfg.nas_key
        else:
            repo = cfg.usb_repo
            os.environ["BORG_PASSPHRASE"] = cfg.usb_key

        os.system("clear")
        print(f"Info des letzten Archivs im {repo} wird aufgelistet...")
        print()
        print(cfg.info(repo)["stdout"])
        print()
        input("Drücken Sie eine beliebige Taste um fortzufahren.")

    # Serverbackup
    elif command in cfg.site_cmds.keys():
        os.system("clear")
        print(f'Websitebackup von "{cfg.site_cmds[command][0]}" wird gestartet...')
        logging.info(f'Websitebackup von "{cfg.site_cmds[command][0]}" wird gestartet.')
        print()
        result_web = cfg.websitebackup(command)

        for site in result_web:
            if result_web[site]["returncode"] == 0:
                print(result_web[site]["msg"])
                logging.info(result_web[site]["msg"])
                print()
            else:
                print(result_web[site]["msg"])
                logging.error(result_web[site]["msg"])
                print()
        time.sleep(4)

    # Syncing backups
    elif command == "sync":
        cfg.rsync_to_synology()

    # No valid command entered
    else:
        os.system("clear")
        print("Bitte geben Sie einen gültigen Befehl aus der Liste ein!")
        print("Gültige Befehle sind:")
        for cmd in valid_cmds:
            print('"' + cmd + '"')
        input("Drücken Sie eine beliebige Taste um fortzufahren...")
