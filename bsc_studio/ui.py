from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPen, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSlider,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import REPOSITORY, __version__
from .openai_provider import REALTIME_VOICES
from .service import NAMES, ROLES, StudioService
from .storage import Preferences
from .updater import GitHubUpdater, start_installer

from .theme import STYLESHEET as STYLESHEET
from .brand import BrandHeader, BrandNavigation
from .storage import resource_dir



def app_icon() -> QIcon:
    logo = resource_dir() / "brand" / "bsc-logo.png"
    if logo.is_file():
        return QIcon(str(logo))
    pixmap = QPixmap(128, 128)
    pixmap.fill(QColor("#101b20"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#d4b36e"), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for x, height in ((30, 25), (47, 48), (64, 76), (81, 48), (98, 25)):
        painter.drawLine(x, 64-height//2, x, 64+height//2)
    painter.end()
    return QIcon(pixmap)


class JobSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    progress = Signal(str)
    finished = Signal()


class Job(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = JobSignals()

    def run(self):
        try:
            self.signals.result.emit(self.function(self.signals.progress.emit))
        except Exception as error:
            message = str(error)
            # Only user-facing, bounded errors; never display request headers or credentials.
            if any(x in message for x in ("Bearer ", "sk-proj-", "github_pat_", "ghp_")):
                message = "L’opération a échoué. Vérifiez vos identifiants et votre connexion."
            self.signals.error.emit(message[:900])
        finally:
            self.signals.finished.emit()


def label(text, name="", wrap=False):
    item = QLabel(text)
    item.setObjectName(name)
    item.setWordWrap(wrap)
    return item


def button(text, function, primary=False):
    item = QPushButton(text.upper())
    item.setCursor(Qt.CursorShape.PointingHandCursor)
    item.setObjectName("primary" if primary else "")
    def invoke():
        try:
            function()
        except Exception as error:
            QMessageBox.warning(item.window(), "BSC Radio Studio", str(error)[:900])
    item.clicked.connect(invoke)
    return item


def table(headers):
    item = QTableWidget(0, len(headers))
    item.setHorizontalHeaderLabels([header.upper() for header in headers])
    item.verticalHeader().hide()
    item.setAlternatingRowColors(True)
    item.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    item.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    item.horizontalHeader().setStretchLastSection(True)
    return item


class MainWindow(QMainWindow):
    def __init__(self, service: StudioService):
        super().__init__()
        self.service = service
        self.current_id = None
        self.dirty = False
        self.loading = False
        self.busy = False
        self.jobs = set()
        self.release = None
        self.setWindowTitle(f"BSC Radio Studio · {__version__}")
        self.setWindowIcon(app_icon())
        self.resize(1320, 940)
        self.setMinimumSize(1100, 820)
        shell = QWidget()
        self.setCentralWidget(shell)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(BrandHeader())
        self.navigation = BrandNavigation()
        layout.addWidget(self.navigation)
        workspace = QWidget()
        workspace.setObjectName("workspace")
        main = QVBoxLayout(workspace)
        main.setContentsMargins(30, 23, 30, 16)
        main.setSpacing(13)
        self.heading = label("VOS ÉPISODES", "heading")
        self.subtitle = label("De l’information au podcast, dans un même espace.", "subheading", True)
        title_row = QHBoxLayout()
        title_row.addWidget(self.heading, 1)
        title_row.addWidget(label("BSC / STUDIO", "sectionTag"))
        main.addLayout(title_row)
        main.addWidget(self.subtitle)
        self.pages = QStackedWidget()
        for build in (self.library_page, self.imports_page, self.editor_page, self.update_page, self.settings_page, self.modules_page):
            self.pages.addWidget(build())
        main.addWidget(self.pages, 1)
        self.progress = QProgressBar()
        self.progress.setFixedHeight(5)
        self.progress.hide()
        self.status = label("Prêt · vos épisodes restent enregistrés sur ce PC.", "hint", True)
        main.addWidget(self.progress)
        footer = QHBoxLayout()
        footer.addWidget(self.status, 1)
        files = button("Mes fichiers", self.open_data)
        files.setObjectName("fileButton")
        footer.addWidget(files)
        main.addLayout(footer)
        layout.addWidget(workspace, 1)
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.8)
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(lambda duration: self.position.setRange(0, duration))
        self.player.errorOccurred.connect(lambda *_: self.status.setText("La lecture audio a échoué. Essayez l’export du fichier."))
        self.navigation.currentRowChanged.connect(self.navigate)
        self.navigation.setCurrentRow(0)
        self.refresh()
        prefs = self.service.preferences
        if prefs.get("check_startup", True) and prefs.get("github_token"):
            QTimer.singleShot(4000, self.check_updates)

    def page(self):
        widget = QWidget()
        box = QVBoxLayout(widget)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(15)
        return widget, box

    def row(self, *widgets):
        row = QHBoxLayout()
        row.setSpacing(10)
        for widget in widgets:
            row.addWidget(widget)
        return row

    def library_page(self):
        page, box = self.page()
        metrics = QHBoxLayout()
        self.metrics = []
        for title in ("ÉPISODES", "INFORMATIONS IMPORTÉES", "AUDIOS À JOUR"):
            card = QFrame()
            card.setObjectName("card")
            content = QVBoxLayout(card)
            content.setContentsMargins(18, 15, 18, 15)
            number = label("0", "metric")
            self.metrics.append(number)
            content.addWidget(number)
            content.addWidget(label(title, "hint"))
            metrics.addWidget(card)
        box.addLayout(metrics)
        box.addLayout(self.row(button("Nouvel épisode", self.new_episode, True), button("Importer un script JSON", self.import_script), button("Ouvrir l’épisode", self.open_selected_episode)))
        self.episode_table = table(["Titre", "État", "Durée", "Modifié le"])
        self.episode_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.episode_table.doubleClicked.connect(self.open_selected_episode)
        box.addWidget(self.episode_table, 1)
        box.addWidget(label("Commencez par importer vos informations, ou créez un épisode pour écrire votre dialogue.", "hint", True))
        return page

    def imports_page(self):
        page, box = self.page()
        fields = QHBoxLayout()
        self.import_title = QLineEdit()
        self.import_title.setPlaceholderText("Titre de l’information")
        self.import_url = QLineEdit()
        self.import_url.setPlaceholderText("https://… · page web ou lien source")
        fields.addWidget(self.import_title)
        fields.addWidget(self.import_url, 2)
        box.addLayout(fields)
        self.import_text = QPlainTextEdit()
        self.import_text.setPlaceholderText("Collez ici un article, vos notes ou les informations à utiliser dans l’émission…")
        self.import_text.setMaximumHeight(135)
        box.addWidget(self.import_text)
        box.addLayout(self.row(button("Ajouter le texte", self.add_text, True), button("Importer la page web", self.add_url), button("Importer TXT / Markdown", self.add_file)))
        box.addWidget(label("Cochez les informations à utiliser, puis créez le dialogue dans Studio.", "hint", True))
        self.items_table = table(["Choix", "Information", "Source", "État"])
        self.items_table.setColumnWidth(0, 60)
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.items_table.setColumnWidth(2, 230)
        box.addWidget(self.items_table, 1)
        box.addLayout(self.row(button("Préparer l’émission", lambda: self.navigation.setCurrentRow(2), True), button("Ajouter un exemple de démonstration", self.add_demo)))
        return page

    def editor_page(self):
        page, box = self.page()
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Titre du podcast")
        self.title_edit.textChanged.connect(self.mark_dirty)
        self.format_combo = QComboBox()
        for identifier, config in self.service.settings.schedule["formats"].items():
            if identifier != "feedback":
                self.format_combo.addItem(config.get("label", identifier), identifier)
        box.addLayout(self.row(self.title_edit, self.format_combo))
        box.addLayout(self.row(button("Générer le dialogue avec GPT", self.generate_script, True), button("Brouillon sans API · démo", self.generate_demo), button("Enregistrer", self.save_episode)))
        self.script_table = QTableWidget(0, 2)
        self.script_table.setHorizontalHeaderLabels(["INTERVENANT", "DIALOGUE"])
        self.script_table.setColumnWidth(0, 145)
        self.script_table.horizontalHeader().setStretchLastSection(True)
        self.script_table.verticalHeader().setDefaultSectionSize(105)
        box.addWidget(self.script_table, 1)
        box.addLayout(self.row(button("+ Ajouter une réplique", self.add_line), button("Retirer la réplique sélectionnée", self.remove_line), button("Exporter le script JSON", self.export_script)))
        box.addWidget(label("Les répliques modifiées seront régénérées ; les prises inchangées sont conservées. Relisez le texte et ses sources avant l’export.", "hint", True))
        box.addLayout(self.row(button("Générer les voix OpenAI", self.render_audio, True), button("Écouter", self.play_audio), button("Arrêter", lambda: self.player.stop()), button("Exporter MP3 / WAV", self.export_audio)))
        self.position = QSlider(Qt.Orientation.Horizontal)
        self.position.setRange(0, 0)
        self.position.sliderMoved.connect(lambda position: self.player.setPosition(position))
        self.playback_time = label("00:00", "hint")
        box.addLayout(self.row(self.position, self.playback_time))
        return page

    def update_page(self):
        page, box = self.page()
        card = QFrame()
        card.setObjectName("card")
        content = QVBoxLayout(card)
        content.setContentsMargins(22, 20, 22, 20)
        content.addWidget(label("VOTRE VERSION", "eyebrow"))
        content.addWidget(label(__version__, "metric"))
        content.addWidget(label("Source : " + REPOSITORY, "subheading"))
        content.addWidget(label("Canal stable · GitHub Releases · vérification SHA-256", "hint"))
        box.addWidget(card)
        self.update_status = label("Vérifiez les nouvelles versions. Pour ce dépôt privé, ajoutez votre jeton GitHub dans Paramètres.", "subheading", True)
        box.addWidget(self.update_status)
        self.release_notes = QPlainTextEdit()
        self.release_notes.setReadOnly(True)
        self.release_notes.setPlaceholderText("Les notes de la prochaine version apparaîtront ici.")
        box.addWidget(self.release_notes, 1)
        self.install_button = button("Télécharger et installer", self.install_update, True)
        self.install_button.setEnabled(False)
        box.addLayout(self.row(button("Vérifier les mises à jour", self.check_updates), self.install_button, button("Voir les versions sur GitHub", self.open_releases)))
        box.addWidget(label("Les mises à jour remplacent le logiciel. Les épisodes, les fichiers audio et les réglages restent dans votre dossier de données.", "hint", True))
        return page

    def settings_page(self):
        page, box = self.page()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)
        form.setSpacing(14)
        prefs = self.service.preferences
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        try:
            self.key_input.setText(prefs.secret("openai_key"))
            self.token_input.setText(prefs.secret("github_token"))
        except RuntimeError as error:
            form.addRow(label(str(error), "hint", True))
        form.addRow(label("OPENAI", "eyebrow"))
        form.addRow("Clé API OpenAI", self.key_input)
        self.text_model = QLineEdit(prefs.get("text_model", "gpt-6-luna"))
        self.voice_model = QLineEdit(prefs.get("voice_model", "gpt-realtime-2.1-mini"))
        form.addRow("Modèle d’écriture", self.text_model)
        form.addRow("Modèle vocal", self.voice_model)
        form.addRow(label("Voix souhaitée : Rivage. Sa disponibilité dans l’API reste à confirmer. Choisissez explicitement les voix proposées pour générer un épisode.", "hint", True))
        self.voice_combos = {}
        for role, name in NAMES.items():
            combo = QComboBox()
            combo.addItem("Choisir une voix API…", "")
            for voice in REALTIME_VOICES:
                combo.addItem(voice.title(), voice)
            combo.setCurrentIndex(max(0, combo.findData(prefs.get("voices", {}).get(role, ""))))
            self.voice_combos[role] = combo
            form.addRow(name, combo)
        form.addRow(label("MISES À JOUR GITHUB", "eyebrow"))
        form.addRow("Dépôt", label(REPOSITORY))
        form.addRow("Jeton du dépôt privé", self.token_input)
        form.addRow(label("Jeton GitHub à accès fin : sélectionnez uniquement BSC-radio, avec Contents en lecture. Il reste chiffré pour votre compte Windows.", "hint", True))
        self.startup_check = QCheckBox("Vérifier les versions au démarrage")
        self.startup_check.setChecked(prefs.get("check_startup", True))
        form.addRow(self.startup_check)
        form.addRow(label("DONNÉES", "eyebrow"))
        form.addRow(label(str(self.service.root), "hint", True))
        form.addRow(button("Sauvegarder la base des épisodes…", self.backup_database))
        scroll.setWidget(inner)
        box.addWidget(scroll, 1)
        box.addWidget(button("Enregistrer les paramètres", self.save_settings, True))
        return page

    def modules_page(self):
        page, box = self.page()
        box.addWidget(label("Un même studio, plusieurs modules", "heading"))
        box.addWidget(label("Le socle est prêt à accueillir les outils de gestion de Brewers Social Club. Le studio podcast est le premier module disponible.", "subheading", True))
        for title, description in (("Imports du site", "Historique, états et erreurs d’import"), ("Statistiques", "Indicateurs du site et de son activité"), ("Bières", "Consultation et gestion du catalogue"), ("Bars", "Gestion des établissements et de leurs informations")):
            card = QFrame()
            card.setObjectName("card")
            content = QVBoxLayout(card)
            content.setContentsMargins(20, 14, 20, 14)
            content.addWidget(label(title + " · à venir"))
            content.addWidget(label(description, "hint"))
            box.addWidget(card)
        box.addStretch()
        return page

    def navigate(self, index):
        if self.current_id and self.dirty:
            try:
                self.save_episode()
            except Exception as error:
                self.error(str(error))
                return
        titles = [("Vos épisodes", "De l’information au podcast, dans un même espace."),
                  ("Les informations", "Importez vos sources et choisissez le contenu de l’émission."),
                  ("Le studio", "Écrivez, ajustez les dialogues et donnez-leur une voix."),
                  ("Les mises à jour", "Suivez les versions publiées sur votre dépôt GitHub."),
                  ("Vos paramètres", "Modèles, voix et connexions pour ce PC."),
                  ("Brewers Social Club", "Une application qui s’étendra module après module.")]
        self.heading.setText(titles[index][0].upper())
        self.subtitle.setText(titles[index][1])
        self.pages.setCurrentIndex(index)

    def error(self, message):
        self.status.setText(message)
        if "GitHub" in message or "dépôt privé" in message:
            self.update_status.setText(message)
        QMessageBox.warning(self, "BSC Radio Studio", message)

    def run_job(self, text, function, done):
        if self.busy:
            return
        self.busy = True
        self.navigation.setEnabled(False)
        self.pages.setEnabled(False)
        self.progress.setRange(0, 0)
        self.progress.show()
        self.status.setText(text)
        job = Job(function)
        self.jobs.add(job)
        job.signals.progress.connect(self.status.setText)
        job.signals.error.connect(self.error)
        job.signals.result.connect(done)
        job.signals.finished.connect(lambda: self.finish_job(job))
        QThreadPool.globalInstance().start(job)

    def finish_job(self, job):
        self.jobs.discard(job)
        self.busy = False
        self.navigation.setEnabled(True)
        self.pages.setEnabled(True)
        self.progress.hide()
        self.refresh()

    def selected_imports(self):
        return [self.items_table.item(row, 0).data(Qt.ItemDataRole.UserRole) for row in range(self.items_table.rowCount())
                if self.items_table.item(row, 0).checkState() == Qt.CheckState.Checked]

    def refresh(self):
        checked = set(self.selected_imports()) if hasattr(self, "items_table") else set()
        episodes, items = self.service.episodes(), self.service.items()
        for metric, value in zip(self.metrics, (len(episodes), len(items), sum(bool(e["audio_path"]) and e["studio_audio_revision"] == e["studio_revision"] for e in episodes))):
            metric.setText(str(value))
        self.episode_table.setRowCount(len(episodes))
        for row, episode in enumerate(episodes):
            ready = episode["audio_path"] and episode["studio_audio_revision"] == episode["studio_revision"]
            values = (episode["title"], "Audio prêt" if ready else "Brouillon", f"{int(episode['duration'] // 60)}:{int(episode['duration'] % 60):02}" if ready else "—", episode["updated_at"])
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, episode["id"])
                self.episode_table.setItem(row, column, cell)
        self.items_table.setRowCount(len(items))
        for row, item in enumerate(items):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            check.setData(Qt.ItemDataRole.UserRole, item["id"])
            check.setCheckState(Qt.CheckState.Checked if item["id"] in checked else Qt.CheckState.Unchecked)
            self.items_table.setItem(row, 0, check)
            for column, value in enumerate((item["title"], item["url"] if not item["url"].startswith("manual:") else "Texte importé", "Faits extraits" if item["status"] == "facts" else "Importé"), 1):
                cell = QTableWidgetItem(value)
                cell.setToolTip(item["raw_text"][:1800] if column == 1 else value)
                self.items_table.setItem(row, column, cell)

    def add_text(self):
        try:
            result = self.service.import_text(self.import_title.text(), self.import_text.toPlainText(), self.import_url.text())
            self.status.setText("Information ajoutée." if result else "Cette information a déjà été importée.")
            self.import_text.clear()
            self.refresh()
        except Exception as error:
            self.error(str(error))

    def add_url(self):
        url = self.import_url.text().strip()
        self.run_job("Lecture de la page web…", lambda progress: self.service.import_url(url),
                     lambda created: self.status.setText("Page importée." if created else "Cette page est déjà présente."))

    def add_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importer un texte", "", "Texte (*.txt *.md)")
        if path:
            try:
                source = Path(path)
                if source.stat().st_size > 2_000_000:
                    raise ValueError("Ce fichier dépasse 2 Mo.")
                self.service.import_text(source.stem, source.read_text(encoding="utf-8-sig"))
                self.refresh()
                self.status.setText("Fichier importé.")
            except Exception as error:
                self.error(str(error))

    def add_demo(self):
        self.service.import_text("Démonstration · la fermentation", "La fermentation transforme les sucres du moût en alcool et en dioxyde de carbone grâce aux levures. Les brasseurs contrôlent la température pendant cette étape. Ce texte sert uniquement à tester le studio.")
        self.refresh()
        for row in range(self.items_table.rowCount()):
            if self.items_table.item(row, 1).text().startswith("Démonstration"):
                self.items_table.item(row, 0).setCheckState(Qt.CheckState.Checked)
        self.status.setText("Exemple ajouté et sélectionné. Utilisez « Brouillon sans API · démo » dans Studio.")

    def new_episode(self):
        if self.current_id and self.dirty:
            self.save_episode()
        episode_id = self.service.create_episode()
        self.open_episode(episode_id)
        self.navigation.setCurrentRow(2)
        self.refresh()

    def open_selected_episode(self):
        row = self.episode_table.currentRow()
        if row < 0:
            self.status.setText("Sélectionnez un épisode à ouvrir.")
            return
        if self.current_id and self.dirty:
            self.save_episode()
        self.open_episode(self.episode_table.item(row, 0).data(Qt.ItemDataRole.UserRole))
        self.navigation.setCurrentRow(2)

    def open_episode(self, episode_id):
        self.loading = True
        self.current_id = episode_id
        self.player.stop()
        self.script_table.setRowCount(0)
        episode = self.service.db.one("SELECT * FROM episode WHERE id=?", (episode_id,))
        self.title_edit.setText(episode["title"])
        self.format_combo.setCurrentIndex(max(0, self.format_combo.findData(episode["format"])))
        for line in self.service.script(episode_id):
            self.add_line(line)
        self.loading = False
        self.dirty = False
        self.status.setText(f"Épisode #{episode_id} ouvert · les modifications sont enregistrées en quittant le studio.")

    def mark_dirty(self, *_):
        if not self.loading and self.current_id:
            self.dirty = True

    def add_line(self, line=None):
        if not self.current_id and not self.loading:
            self.new_episode()
            return
        if not isinstance(line, dict):
            line = {"character": "presenter", "text": "", "fact_ids": [], "delivery": []}
        row = self.script_table.rowCount()
        self.script_table.insertRow(row)
        combo = QComboBox()
        for name, role in ROLES.items():
            combo.addItem(name, role)
        combo.setCurrentIndex(max(0, combo.findData(line.get("character", "presenter"))))
        combo.currentIndexChanged.connect(self.mark_dirty)
        text = QPlainTextEdit(line.get("text", ""))
        text.setPlaceholderText("Texte de la réplique…")
        text.setProperty("line_data", line)
        text.textChanged.connect(self.mark_dirty)
        self.script_table.setCellWidget(row, 0, combo)
        self.script_table.setCellWidget(row, 1, text)
        self.mark_dirty()

    def remove_line(self):
        row = self.script_table.currentRow()
        if row >= 0:
            self.script_table.removeRow(row)
            self.mark_dirty()

    def editor_lines(self):
        lines = []
        for row in range(self.script_table.rowCount()):
            editor = self.script_table.cellWidget(row, 1)
            previous = editor.property("line_data") or {}
            lines.append({**previous, "character": self.script_table.cellWidget(row, 0).currentData(), "text": editor.toPlainText().strip()})
        return lines

    def save_episode(self):
        if self.current_id:
            self.service.save_script(self.current_id, self.title_edit.text(), self.editor_lines())
            self.dirty = False
            self.status.setText("Script enregistré.")

    def import_script(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importer un script", "", "Script JSON (*.json)")
        if not path:
            return
        try:
            source = Path(path)
            if source.stat().st_size > 2_000_000:
                raise ValueError("Le script dépasse 2 Mo.")
            data = json.loads(source.read_text(encoding="utf-8-sig"))
            script = data.get("script", data.get("lines"))
            if not isinstance(script, list) or not script:
                raise ValueError("Le JSON doit contenir une liste « script » de répliques.")
            lines = []
            for line in script:
                if not isinstance(line, dict) or not isinstance(line.get("text"), str):
                    raise ValueError("Chaque réplique doit contenir un texte et un personnage.")
                role = ROLES.get(line.get("character"), line.get("character", "presenter"))
                if role not in NAMES:
                    raise ValueError("Personnage inconnu : " + str(role))
                lines.append({"character": role, "text": line["text"], "delivery": [], "fact_ids": [], "feedback_ids": []})
            episode_id = self.service.create_episode(data.get("title", source.stem), lines, data.get("format", "journal"))
            self.open_episode(episode_id)
            self.navigation.setCurrentRow(2)
            self.refresh()
        except Exception as error:
            self.error(str(error))

    def generate_script(self):
        self.generate(False)

    def generate_demo(self):
        self.generate(True)

    def generate(self, demo):
        if self.current_id and self.dirty:
            self.save_episode()
        item_ids = self.selected_imports()
        title = self.title_edit.text().strip() or ("Démonstration du studio" if demo else "Nouvelle émission")
        fmt = self.format_combo.currentData()
        self.run_job("Préparation de l’émission…", lambda progress: self.service.generate_script(title, fmt, item_ids, progress, demo), self.on_script_created)

    def on_script_created(self, episode_id):
        self.open_episode(episode_id)
        self.status.setText("Dialogue créé. Relisez les répliques avant de produire les voix.")

    def export_script(self):
        if not self.current_id:
            self.status.setText("Créez ou ouvrez un épisode.")
            return
        self.save_episode()
        path, _ = QFileDialog.getSaveFileName(self, "Exporter le script", "episode.json", "Script JSON (*.json)")
        if path:
            try:
                data = {"title": self.title_edit.text(), "format": self.format_combo.currentData(), "script": self.editor_lines()}
                Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                self.status.setText("Script exporté.")
            except Exception as error:
                self.error(str(error))

    def render_audio(self):
        if not self.current_id:
            self.status.setText("Créez ou ouvrez un épisode.")
            return
        self.save_episode()
        self.player.stop()
        episode_id = self.current_id
        self.run_job("Préparation des voix…", lambda progress: self.service.render(episode_id, progress),
                     lambda path: self.status.setText("Audio produit. Écoutez-le avant l’export."))

    def play_audio(self):
        if not self.current_id:
            return
        try:
            self.save_episode()
            path = self.service.current_audio(self.current_id)
            self.player.setSource(QUrl.fromLocalFile(str(path)))
            self.player.play()
        except Exception as error:
            self.error(str(error))

    def update_position(self, position):
        if not self.position.isSliderDown():
            self.position.setValue(position)
        seconds = position // 1000
        self.playback_time.setText(f"{seconds // 60:02}:{seconds % 60:02}")

    def export_audio(self):
        if not self.current_id:
            return
        try:
            self.save_episode()
            self.service.current_audio(self.current_id)
        except Exception as error:
            self.error(str(error))
            return
        path, chosen = QFileDialog.getSaveFileName(self, "Exporter le podcast", f"episode-{self.current_id}.mp3", "MP3 (*.mp3);;WAV (*.wav)")
        if path:
            target = Path(path)
            if target.suffix.lower() not in (".mp3", ".wav"):
                target = target.with_suffix(".wav" if chosen.startswith("WAV") else ".mp3")
            episode_id = self.current_id
            self.run_job("Export du podcast…", lambda progress: self.service.export_audio(episode_id, target),
                         lambda _: self.status.setText("Podcast exporté : " + str(target)))

    def save_settings(self):
        try:
            text_model, voice_model = self.text_model.text().strip(), self.voice_model.text().strip()
            if not text_model or not voice_model:
                raise ValueError("Renseignez les modèles d’écriture et de voix.")
            self.service.preferences.save({"text_model": text_model, "voice_model": voice_model,
                "voices": {role: combo.currentData() for role, combo in self.voice_combos.items()},
                "check_startup": self.startup_check.isChecked()},
                {"openai_key": self.key_input.text().strip(), "github_token": self.token_input.text().strip()})
            self.status.setText("Paramètres enregistrés · identifiants chiffrés pour ce compte Windows.")
        except Exception as error:
            self.error(str(error))

    def check_updates(self):
        if self.busy:
            return
        try:
            token = Preferences(self.service.root).secret("github_token")
        except Exception as error:
            self.error(str(error))
            return
        self.update_status.setText("Recherche de la dernière version stable…")
        self.run_job("Connexion à GitHub…", lambda progress: GitHubUpdater(token).check(), self.on_release)

    def on_release(self, release):
        self.release = release
        self.install_button.setEnabled(bool(release))
        if release:
            self.update_status.setText(f"La version {release.version} est disponible.")
            self.release_notes.setPlainText(release.notes or "Aucune note de version.")
            self.status.setText(f"Mise à jour {release.version} disponible dans l’onglet Mises à jour.")
        else:
            self.update_status.setText("Aucune nouvelle version stable disponible. Votre version est à jour ou la première Release n’a pas encore été publiée.")
            self.status.setText("Vérification des versions terminée.")

    def install_update(self):
        if not self.release:
            return
        if self.current_id and self.dirty:
            self.save_episode()
        release = self.release
        token = Preferences(self.service.root).secret("github_token")
        self.run_job("Téléchargement de l’installeur…", lambda progress: GitHubUpdater(token).download(
            release, self.service.root / "updates", lambda value: progress(f"Téléchargement de la version {release.version} · {value} %")), self.on_installer)

    def on_installer(self, path):
        self.status.setText("Téléchargement terminé et empreinte SHA-256 vérifiée.")
        self.pending_installer = path
        QTimer.singleShot(100, self.confirm_install)

    def confirm_install(self):
        answer = QMessageBox.question(self, "Mise à jour prête", "L’installeur a été téléchargé et vérifié. Fermer le studio et ouvrir l’assistant de mise à jour ?\nVos données seront conservées.")
        if answer == QMessageBox.StandardButton.Yes:
            try:
                start_installer(self.pending_installer)
                self.close()
            except Exception as error:
                self.error(str(error))

    def backup_database(self):
        path, _ = QFileDialog.getSaveFileName(self, "Sauvegarder la base", "BSC-radio-sauvegarde.sqlite3", "Base SQLite (*.sqlite3)")
        if path:
            try:
                if Path(path).resolve() == self.service.db.path.resolve():
                    raise ValueError("Choisissez un autre fichier que la base active.")
                self.service.backup(Path(path))
                self.status.setText("Base sauvegardée. Copiez également le dossier audio pour sauvegarder les enregistrements.")
            except Exception as error:
                self.error(str(error))

    def open_data(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.service.root)))

    def open_releases(self):
        QDesktopServices.openUrl(QUrl(f"https://github.com/{REPOSITORY}/releases"))

    def closeEvent(self, event):
        if self.busy:
            self.status.setText("L’opération est encore en cours. Attendez sa fin avant de fermer le studio.")
            event.ignore()
            return
        if self.current_id and self.dirty:
            try:
                self.save_episode()
            except Exception as error:
                self.error(str(error))
                event.ignore()
                return
        self.player.stop()
        super().closeEvent(event)
