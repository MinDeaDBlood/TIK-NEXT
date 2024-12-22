#!/usr/bin/env python
import hashlib
import json
import platform as plat
import re
import shutil
import subprocess
import sys
import time
import zipfile
from io import BytesIO
from os import path as o_path
import banner
import ext4
from Magisk import Magisk_patch
import os
from dumper import Dumper
import extract_dtb
import requests
from rich.progress import track
import contextpatch
import downloader
import fspatch
import imgextractor
import lpunpack
import mkdtboimg
import ofp_mtk_decrypt
import ofp_qc_decrypt
import ozipdecrypt
import utils
from api import cls, dir_has, cat, dirsize, re_folder, f_remove
from log import LOGS, LOGE, ysuc, yecho, ywarn
from utils import gettype, simg2img, call
import opscrypto
from rich.table import Table
from rich.console import Console

# Устанавливаем директорию языка
LANGUAGE_DIR = o_path.join(os.getcwd(), "language")

# Устанавливаем начальный язык
current_language = 'en'  # Или 'en', в зависимости от предпочтений пользователя

def load_language(lang):
    """Загружает языковые ресурсы из JSON файла."""
    try:
        filepath = o_path.join(LANGUAGE_DIR, f'translations_{lang}.json')
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Language file not found. Falling back to default (English).")
        return load_language('en')  # Если файл не найден, используйте английский.

translations = load_language(current_language)

class json_edit:
    def __init__(self, j_f):
        self.file = j_f

    def read(self):
        if not os.path.exists(self.file):
            return {}
        try:
            with open(self.file, 'r+', encoding='utf-8') as pf:
                return json.load(pf)
        except (json.JSONDecodeError, Exception) as e:
            ywarn(f"Ошибка чтения JSON файла: {e}")
            return {}

    def write(self, data):
        with open(self.file, 'w+', encoding='utf-8') as pf:
            json.dump(data, pf, indent=4)

    def edit(self, name, value):
        data = self.read()
        data[name] = value
        self.write(data)


def rmdire(path):
    """Удаляет директорию и все ее содержимое."""
    if o_path.exists(path):
        try:
            shutil.rmtree(path)
            ysuc(translations["remove_successful"])
        except PermissionError:
            ywarn(translations["permission_error"])
        except Exception as e:
            ywarn(f"{translations['error_removing']}: {e}")


def error(exception_type, exception, traceback):
    """Обработка ошибок."""
    cls()
    table = Table()
    version = getattr(settings, 'version', translations["unknown"])
    table.add_column(f'[red]{translations["error"]}:{exception_type.__name__}[/]', justify="center")
    table.add_row(f'[yellow]{translations["description"]}:{exception}')
    table.add_row(f'[yellow]{translations["line"]}:{exception.__traceback__.tb_lineno}\t{translations["module"]}:{exception.__traceback__.tb_frame.f_globals["__name__"]}')
    table.add_row(f'[blue]{translations["platform"]}:{plat.machine()}\t[blue]{translations["system"]}:{plat.uname().system} {plat.uname().release}')
    table.add_row(f'[blue]{translations["python"]}:{sys.version[:6]}\t[blue]{translations["version"]}:{version}')
    table.add_row(f'[green]{translations["issue_report"]}')
    Console().print(table)
    input()
    sys.exit(1)


def sha1(file_path):
    """Вычисляет SHA1 хэш файла."""
    if os.path.exists(file_path):
        with open(file_path, 'rb') as f:
            return hashlib.sha1(f.read()).hexdigest()
    return ''


if not os.path.exists(ebinner):
    raise Exception(translations["binary_file_not_found"])

try:
    if os.path.basename(sys.argv[0]) == f'run_new{str() if os.name == "posix" else ".exe"}':
        os.remove(os.path.join(LOCALDIR, f'run{str() if os.name == "posix" else ".exe"}'))
        shutil.copyfile(os.path.join(LOCALDIR, f'run_new{str() if os.name == "posix" else ".exe"}'),
                        os.path.join(LOCALDIR, f'run{str() if os.name == "posix" else ".exe"}'))
    elif os.path.basename(sys.argv[0]) == f'run{str() if os.name == "posix" else ".exe"}':
        new = os.path.join(LOCALDIR, f'run_new{str() if os.name == "posix" else ".exe"}')
        if os.path.exists(new) and sha1(os.path.join(LOCALDIR, f'run{str() if os.name == "posix" else ".exe"}')) == sha1(new):
            os.remove(new)
        else:
            subprocess.Popen([new])
            sys.exit()
except Exception as e:
    ywarn(f"{translations['error_during_update']}: {e}")

class set_utils:
    def __init__(self, path):
        self.path = path

    def load_set(self):
        with open(self.path, 'r') as ss:
            data = json.load(ss)
            [setattr(self, v, data[v]) for v in data]

    def change(self, name, value):
        with open(self.path, 'r') as ss:
            data = json.load(ss)
        with open(self.path, 'w', encoding='utf-8') as ss:
            data[name] = value
            json.dump(data, ss, ensure_ascii=False, indent=4)
        self.load_set()


settings = set_utils(setfile)
settings.load_set()


class upgrade:
    update_json = 'https://mirror.ghproxy.com/https://raw.githubusercontent.com/ColdWindScholar/Upgrade/main/TIK.json'

    def __init__(self):
        if not os.path.exists(temp):
            os.makedirs(temp)
        cls()
        with Console().status(translations["checking_for_updates"]):
            try:
                data = requests.get(self.update_json).json()
            except (requests.RequestException, json.JSONDecodeError):
                data = None
        
        if data:
            if data.get('version', settings.version) != settings.version:
                print(f'\033[31m {banner.banner1} \033[0m')
                print(f"{translations['new_version']} {settings.version} --> {data.get('version')}")
                print(f"{translations['changes']}\n{data.get('log', translations['fixing_errors'])}")
                if input(translations["upgrade_prompt"]) == '1':
                    self.download_and_update(data)
            else:
                input(translations["latest_version"])

    def download_and_update(self, data):
        try:
            link = data['link'][plat.system()][plat.machine()]
            if link:
                print(translations["downloading_new_version"])
                downloader.download([link], temp)
                self.extract_and_install_update(link)
        except Exception:
            input(translations["update_not_found"])

    def extract_and_install_update(self, link):
        print(translations["updating_please_wait"])
        upgrade_pkg = os.path.join(temp, os.path.basename(link))
        extract_path = os.path.join(temp, 'update')
        rmdire(extract_path)
        
        try:
            zipfile.ZipFile(upgrade_pkg).extractall(extract_path)
        except (zipfile.BadZipFile, Exception):
            input(translations["corrupted_update_file"])
            return
        
        self.update_settings(extract_path)

    def update_settings(self, extract_path):
        self.settings = json_edit(setfile).read()
        json2 = json_edit(os.path.join(extract_path, 'bin', 'settings.json')).read()
        
        for i in self.settings.keys():
            json2[i] = self.settings.get(i, json2.get(i, ''))
        
        json2['version'] = self.version
        shutil.copytree(os.path.join(extract_path, 'bin'), os.path.join(LOCALDIR, 'bin2'), dirs_exist_ok=True)
        shutil.move(os.path.join(extract_path, f'run{str() if os.name == "posix" else ".exe"}'),
                    os.path.join(LOCALDIR, f'run_new{str() if os.name == "posix" else ".exe"}'))
        rmdire(os.path.join(LOCALDIR, 'bin'))
        shutil.copytree(os.path.join(LOCALDIR, 'bin2'), os.path.join(LOCALDIR, 'bin'))
        rmdire(os.path.join(LOCALDIR, 'bin2'))
        json_edit(setfile).write(json2)

        input(translations["restart_prompt"])
        subprocess.Popen([os.path.join(LOCALDIR, f'run_new{str() if os.name == "posix" else ".exe"}')])
        sys.exit()


class setting:
    def settings1(self):
        actions = {
            "1": lambda: settings.change('brcom', self.get_brotli_compression_level()),
            "2": lambda: settings.change('diysize', self.get_dynamic_size()),
            "3": lambda: settings.change('pack_e2', self.get_pack_e2()),
            "6": lambda: settings.change('pack_sparse', self.get_pack_sparse()),
            "7": lambda: settings.change('diyimgtype', self.get_diy_image_type()),
            "8": lambda: settings.change('erofs_old_kernel', self.get_erofs_old_kernel())
        }
        cls()
        print(self.settings_menu())
        op_pro = input(translations["please_make_a_choice"])
        if op_pro in actions:
            actions[op_pro]()
        else:
            print(translations["error_input"])
        self.settings1()

    def settings2(self):
        cls()
        actions = {
            '1': lambda: settings.change('super_group', self.get_super_group()),
            '2': lambda: settings.change('metadatasize', self.get_metadata_size()),
            '3': lambda: settings.change('BLOCKSIZE', self.get_block_size()),
            '4': lambda: settings.change('SBLOCKSIZE', self.get_sblock_size()),
            '5': lambda: settings.change('supername', self.get_super_name()),
            '6': lambda: settings.change('fullsuper', self.get_full_super()),
            '7': lambda: settings.change('autoslotsuffixing', self.get_auto_slot_suffixing())
        }
        print(self.settings_dynamic_partition_menu())
        op_pro = input(translations["please_enter_number"])
        if op_pro in actions:
            actions[op_pro]()
        else:
            ywarn(translations["error_input"])
        self.settings2()

    def settings3(self):
        cls()
        print(self.settings_program_menu())
        op_pro = input(translations["please_enter_number"])
        actions = {
            '1': self.set_banner,
            '2': self.toggle_online,
            '3': self.toggle_context,
            '4': upgrade,
        }
        if op_pro in actions:
            actions[op_pro]()
        else:
            print(translations["error_input"])
        self.settings3()

    @staticmethod
    def settings_menu():
        return f'''
        \033[33m  > Настройки сборки \033[0m
           1> Уровень сжатия Бротли \033[93m[{settings.brcom}]\033[0m\n
           ----[Настройки EXT4]------
           2> Настройка размера \033[93m[{settings.diysize}]\033[0m
           3> Способ сборки \033[93m[{settings.pack_e2}]\033[0m\n
           ----[Настройки EROFS]-----
           4> Способ сжатия \033[93m[{settings.erofslim}]\033[0m\n
           ----[Настройки IMG]-------
           5> Временная метка UTC \033[93m[{settings.utcstamp}]\033[0m
           6> Создание sparse образа \033[93m[{settings.pack_sparse}]\033[0m
           7> Выбор типа файловой системы \033[93m[{settings.diyimgtype}]\033[0m
           8> Поддержка старых ядер \033[93m[{settings.erofs_old_kernel}]\033[0m\n
           0> Вернуться назад
           --------------------------
        '''

    @staticmethod
    def settings_dynamic_partition_menu():
        return f'''
        \033[33m  > Настройки динамического раздела \033[0m
           1> Название группы динамического раздела \033[93m[{settings.super_group}]\033[0m\n
           ----[Настройки метаданных]--
           2> Максимальный размер \033[93m[{settings.metadatasize}]\033[0m\n
           ----[Настройки раздела]------
           3> Размер сектора/блока по умолчанию \033[93m[{settings.BLOCKSIZE}]\033[0m\n
           ----[Настройки Super образа]-----
           4> Выбрать размер блока \033[93m[{settings.SBLOCKSIZE}]\033[0m
           5> Изменить название Super образа \033[93m[{settings.supername}]\033[0m
           6> Создание полного Super образа \033[93m[{settings.fullsuper}]\033[0m
           7> Добавление A/B структуры разделов \033[93m[{settings.autoslotsuffixing}]\033[0m\n
           0> Вернуться назад
           --------------------------
        '''

    @staticmethod
    def settings_program_menu():
        return f'''
        \033[33m  > Настройки программы \033[0m\n
           1> Настройка баннера на главной странице \033[93m[{settings.banner}]\033[0m\n
           2> Включить/отключить сообщения дня \033[93m[{settings.online}]\033[0m\n
           3> Исправить Contexts \033[93m[{settings.context}]\033[0m\n
           4> Проверка обновлений \n
           0> Вернуться назад\n
           --------------------------
        '''

    @staticmethod
    def settings_initial_menu():
        return f'''
        \033[33m  > Настройки \033[0m
           1> Настройки упаковки\n
           2> Настройки динамического раздела\n
           3> Настройки программы\n
           4> О программе\n
           0> Вернуться в главное меню
           --------------------------
        '''


def plug_parse(js_on):
    class parse:
        gavs = {}

        def __init__(self, jsons):
            self.value = []
            print("""
    ------------------
    MIO-АНАЛИЗАТОР ПАКЕТОВ
    ------------------
                  """)
            try:
                with open(jsons, 'r', encoding='UTF-8') as f:
                    data_ = json.load(f)
                plugin_title = data_['main']['info']['title']
                print("----------" + plugin_title + "----------")
                for group_name, group_data in data_['main'].items():
                    if group_name != "info":
                        for con in group_data['controls']:
                            if 'set' in con:
                                self.value.append(con['set'])
                            if con["type"] == "text":
                                if con['text'] != plugin_title:
                                    print("----------" + con['text'] + "----------")
                            elif con["type"] == "filechose":
                                file_var_name = con['set']
                                ysuc(translations["please_drag_file"])
                                self.gavs[file_var_name] = input(con['text'])
                            elif con["type"] == "radio":
                                self.handle_radio(con)
                            elif con["type"] == 'input':
                                self.handle_input(con)
                            elif con['type'] == 'checkbutton':
                                self.handle_checkbutton(con)
                            else:
                                print(f"{translations['unsupported_parsing']}: %s" % con['type'])

            except Exception as e:
                ywarn(f"Ошибка анализа {e}")

        def handle_radio(self, con):
            gavs = {}
            radio_var_name = con['set']
            options = con['opins'].split()
            cs = 0
            print("-------Выбор варианта---------")
            for option in options:
                cs += 1
                text, value = option.split('|')
                self.gavs[radio_var_name] = value
                print(f"[{cs}] {text}")
                gavs[str(cs)] = value
            print("---------------------------")
            op_in = input(translations["please_enter_number"])
            self.gavs[radio_var_name] = gavs.get(op_in, gavs["1"])

        def handle_input(self, con):
            input_var_name = con['set']
            if 'text' in con:
                print(con['text'])
            self.gavs[input_var_name] = input(translations["please_enter_input"])

        def handle_checkbutton(self, con):
            b_var_name = con['set']
            text = translations['M.K.C'] if 'text' not in con else con['text']
            self.gavs[b_var_name] = 1 if input(text + translations["yes_no_question"]) == '1' else 0

    data = parse(js_on)
    return data.gavs, data.value


class Tool:
    """Основной класс программы."""

    def __init__(self):
        self.pro = None

    def main(self):
        projects = {}
        pro = 0
        cls()
        if settings.banner != "6":
            print(f'\033[31m {getattr(banner, "banner%s" % settings.banner)} \033[0m')
        else:
            print("=" * 50)
        print("\033[93;44m Альфа версия \033[0m")

        if settings.online == 'true':
            self.display_quote()
        
        print(" >\033[33m Список проектов \033[0m\n")
        self.display_projects(projects)

        op_pro = input(translations["please_enter_number"])
        self.process_user_input(op_pro, projects)

    def display_quote(self):
        """Отображает цитату."""        
        try:
            content = json.loads(requests.get('https://v1.jinrishici.com/all.json', timeout=2).content.decode())
            shiju = content['content']
            fr = content['origin']
            another = content['author']
            print(f"\033[36m “{shiju}”")
            print(f"\033[36m---{another}《{fr}》\033[0m\n")
        except (requests.RequestException, json.JSONDecodeError):
            print(f"\033[36m “Открытый исходный код — это движение вперед без вопросов”\033[0m\n")

    def display_projects(self, projects):
        """Отображает доступные проекты."""
        print("\033[31m   [00]  Удалить проект\033[0m\n\n", "  [0]  Создать новый проект\n")
        for pros in os.listdir(LOCALDIR):
            if pros == 'bin' or pros.startswith('.'):
                continue
            if os.path.isdir(o_path.join(LOCALDIR, pros)):
                pro += 1
                print(f"   [{pro}]  {pros}\n")
                projects[str(pro)] = pros

    def process_user_input(self, op_pro, projects):
        """Обрабатывает пользовательский ввод."""
        if op_pro == '55':
            self.unpackrom()
        elif op_pro == '88':
            url = input(translations["input_download_url"])
            if url:
                try:
                    downloader.download([url], LOCALDIR)
                except Exception as e:
                    ywarn(f"Ошибка при скачивании: {e}")
                self.unpackrom()
        elif op_pro == '00':
            self.delete_project(projects)
        elif op_pro == '0':
            self.create_new_project()
        elif op_pro == '66':
            cls()
            ysuc(translations["thank_you_use_tool"])
            sys.exit(0)
        elif op_pro == '77':
            setting()
        elif op_pro.isdigit() and op_pro in projects.keys():
            self.pro = projects[op_pro]
            self.project()
        else:
            ywarn(translations["error_input"])
            input(translations["press_any_key_continue"])
        
        self.main()

    def delete_project(self, projects):
        """Удаляет проект."""
        op_pro = input(translations["input_project_number_to_delete"])
        op_pro = op_pro.split() if " " in op_pro else [op_pro]
        for op in op_pro:
            if op in projects.keys():
                if input(f"  Удалить {projects[op]}? [1/0]") == '1':
                    rmdire(o_path.join(LOCALDIR, projects[op]))
                else:
                    ywarn(translations["restore"])

    def create_new_project(self):
        """Создает новый проект."""
        projec = input(translations["input_project_name"])
        if projec:
            if os.path.exists(o_path.join(LOCALDIR, projec)):
                projec = f'{projec}_{time.strftime("%m%d%H%M%S")}'
                ywarn(f"Проект уже существует! Называется: {projec}")
            os.makedirs(o_path.join(LOCALDIR, projec, "config"))
            self.pro = projec
            self.project()
        else:
            ywarn(translations["error_input"])
            input(translations["press_any_key_continue"])

    def project(self):
        """Управляет проектом."""
        project_dir = LOCALDIR + os.sep + self.pro
        cls()
        os.chdir(project_dir)
        print(f" \033[31m> Меню проекта \033[0m\n")
        print(f"  Проект: {self.pro}\n")
        
        if not os.path.exists(project_dir + os.sep + 'TI_out'):
            os.makedirs(project_dir + os.sep + 'TI_out')

        print('\033[33m    0> Вернуться в главное меню          2> Меню распаковки\033[0m\n')
        print('\033[36m    3> Меню упаковки                     4> Меню плагинов\033[0m\n')
        print('\033[32m    5> Собрать в zip архив               6> Установка магиска (рута), удаление avb, шифрования\033[0m\n')

        op_menu = input(translations["please_enter_number"])
        self.handle_project_option(op_menu, project_dir)

    def handle_project_option(self, op_menu, project_dir):
        """Обрабатывает действия в меню проекта."""
        if op_menu == '0':
            os.chdir(LOCALDIR)
            return
        elif op_menu == '2':
            unpack_choo(project_dir)
        elif op_menu == '3':
            packChoo(project_dir)
        elif op_menu == '4':
            subbed(project_dir)
        elif op_menu == '5':
            self.hczip()
        elif op_menu == '6':
            self.custom_rom()
        else:
            ywarn(translations["error_input"])
            input(translations["press_any_key_continue"])

        self.project()

    def custom_rom(self):
        """Кастомизация ROM."""
        cls()
        print(" \033[31m>Функции для продвинутых пользователей \033[0m\n")
        print(f"  Проект: {self.pro}\n")
        print('\033[33m    0> Вернуться назад                 1> Установить магиск в образ, для получения рута\033[0m\n')
        print('\033[33m    2> Удалить avb                     3> Удалить шифрование данных\033[0m\n')

        op_menu = input(translations["please_enter_number"])
        if op_menu == '0':
            return
        elif op_menu == '1':
            self.magisk_patch()
        elif op_menu == '2':
            self.remove_avb_from_images()
        elif op_menu == '3':
            self.remove_data_encryption_from_images()
        else:
            ywarn(translations["error_input"])

        input(translations["press_any_key_continue"])
        self.custom_rom()

    def magisk_patch(self):
        """Патч образа с помощью Magisk."""
        cs = 0
        project = LOCALDIR + os.sep + self.pro
        os.chdir(LOCALDIR)
        print(" \033[31m> Установка магиска (рута) \033[0m\n")
        print(f"  Проект: {self.pro}\n")
        print(f"  Пожалуйста, выберите образ, в который нужно установить магиск {project}")
        
        boots = {}
        for i in os.listdir(project):
            if os.path.isdir(os.path.join(project, i)):
                continue
            if gettype(os.path.join(project, i)) in ['boot', 'vendor_boot']:
                cs += 1
                boots[str(cs)] = os.path.join(project, i)
                print(f'  [{cs}]--{i}')

        print("\033[33m-------------------------------\033[0m")
        print("\033[33m    [00] Назад\033[0m\n")

        op_menu = input(translations["please_enter_number"])
        if op_menu in boots.keys():
            mapk = input(translations["choose_magisk_apk_path"])
            if not os.path.isfile(mapk):
                ywarn(translations["input_error"])
            else:
                patch = Magisk_patch(boots[op_menu], '', MAGISAPK=mapk)
                patch.auto_patch()
                self.handle_successful_patch(project, boots, op_menu)
        elif op_menu == '00':
            os.chdir(project)
            return
        else:
            ywarn(translations["input_error"])

    def handle_successful_patch(self, project, boots, op_menu):
        """Обрабатывает успешное завершение патча."""
        if os.path.exists(os.path.join(LOCALDIR, 'new-boot.img')):
            out = os.path.join(project, "boot_patched.img")
            shutil.move(os.path.join(LOCALDIR, 'new-boot.img'), out)
            LOGS(f"Moved to: {out}")
            LOGS(translations["installation_successful"])
        else:
            LOGE(translations["installation_failed"])

    def remove_avb_from_images(self):
        """Удаляет AVB из образов в проекте."""
        for root, dirs, files in os.walk(LOCALDIR + os.sep + self.pro):
            for file in files:
                if file.startswith("fstab."):
                    self.dis_avb(os.path.join(root, file))

    def remove_data_encryption_from_images(self):
        """Удаляет шифрование данных из образов в проекте."""
        for root, dirs, files in os.walk(LOCALDIR + os.sep + self.pro):
            for file in files:
                if file.startswith("fstab."):
                    self.dis_data_encryption(os.path.join(root, file))

    def hczip(self):
        """Упаковка прошивки."""
        cls()
        project = LOCALDIR + os.sep + self.pro
        print(" \033[31m> Упаковка прошивки \033[0m\n")
        print(f"  Проект: {os.path.basename(project)}\n")
        print('\033[33m    1> Собрать прошивку в zip архив     2> Собрать прошивку и добавить в zip архив скрипт, чтобы прошивку можно было прошить через fastboot используя ПК и через TWRP\nOFOX \n    3> Вернуться назад\033[0m\n')

        chose = input(translations["please_enter_number"])
        if chose == '1':
            self.prepare_for_zip()
        elif chose == '2':
            utils.dbkxyt(os.path.join(project, 'TI_out') + os.sep, input(translations["zip_creation_prompt"]),
                         binner + os.sep + 'extra_flash.zip')
        else:
            return

        zip_file(os.path.basename(project) + ".zip", project + os.sep + 'TI_out', project + os.sep, LOCALDIR + os.sep)

    def prepare_for_zip(self):
        """Готовит проект к упаковке в zip архив."""
        print(translations["preparing_for_zip"])
        for v in ['firmware-update', 'META-INF', 'exaid.img', 'dynamic_partitions_op_list']:
            if os.path.isdir(os.path.join(project, v)):
                if not os.path.isdir(os.path.join(project, 'TI_out' + os.sep + v)):
                    shutil.copytree(os.path.join(project, v), os.path.join(project, 'TI_out' + os.sep + v))
            elif os.path.isfile(os.path.join(project, v)):
                if not os.path.isfile(os.path.join(project, 'TI_out' + os.sep + v)):
                    shutil.copy(os.path.join(project, v), os.path.join(project, 'TI_out'))

    def unpackrom(self):
        """Распаковывает ROM."""
        cls()
        zipn = 0
        zips = {}
        print(" \033[31m > Список прошивок \033[0m\n")
        ywarn(translations["zip_selection_prompt"])

        if dir_has(LOCALDIR, '.zip'):
            for zip0 in os.listdir(LOCALDIR):
                if zip0.endswith('.zip'):
                    if os.path.isfile(os.path.abspath(zip0)) and os.path.getsize(os.path.abspath(zip0)):
                        zipn += 1
                        print(f"   [{zipn}]- {zip0}\n")
                        zips[zipn] = zip0
        else:
            ywarn(translations["no_rom_files"])

        print("--------------------------------------------------\n")
        zipd = input(translations["please_enter_number"])
        if zipd.isdigit() and int(zipd) in zips.keys():
            self.create_new_project_from_zip(zips[int(zipd)])
        else:
            ywarn(translations["error_input"])
            input(translations["press_any_key_continue"])

    def create_new_project_from_zip(self, zip_file_name):
        """Создает новый проект на основе выбранного zip файла."""
        projec = input(translations["input_project_name"])
        project = f"TI_{projec}" if projec else f"TI_{os.path.basename(zip_file_name).replace('.zip', '')}"
        
        if os.path.exists(o_path.join(LOCALDIR, project)):
            project = f"{project}_{time.strftime('%m%d%H%M%S')}"
            ywarn(f"Проект уже существует! Называется: {project}")

        os.makedirs(o_path.join(LOCALDIR, project))
        print(f"{project} создан успешно！")
        
        with Console().status(translations["unpacking"]):
            zipfile.ZipFile(os.path.abspath(zip_file_name)).extractall(o_path.join(LOCALDIR, project))
        
        yecho(translations["unpacking_successful"])
        autounpack(o_path.join(LOCALDIR, project))

        self.pro = project
        self.project()

def get_all_file_paths(directory):
    """Генерирует полные пути всех файлов в заданной директории."""
    for root, directories, files in os.walk(directory):
        for filename in files:
            yield os.path.join(root, filename)

class zip_file:
    def __init__(self, file, dst_dir, local, path=None):
        if not path:
            path = LOCALDIR + os.sep
        os.chdir(dst_dir)
        relpath = str(path + file)
        if os.path.exists(relpath):
            ywarn(f"{translations['file_already_exists']}: {file} , был автоматически переименован в {(relpath := path + utils.v_code() + file)}")
        
        with zipfile.ZipFile(relpath, 'w', compression=zipfile.ZIP_DEFLATED,
                             allowZip64=True) as zip_:
            for file in get_all_file_paths('.'):
                print(f"{translations['writing']}: {file}")
                try:
                    zip_.write(file)
                except Exception as e:
                    print(f"{translations['write_error']}: {e}")

        if os.path.exists(relpath):
            print(f"{translations['packing_complete']}: {relpath}")
        os.chdir(local)

if __name__ == '__main__':
    Tool().main()
