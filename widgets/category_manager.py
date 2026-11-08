"""Gestion des catégories (dialogue modal : capture le focus clavier)."""
import random

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (QColorDialog, QDialog, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QComboBox, QMessageBox, QVBoxLayout,
                               QKeySequenceEdit)

from widgets.controls import GlassButton, GlassCombo
from config import MAX_NAME_LEN, ConfigManager, validate_categories
from models import Category

PASTELS = ["#0a84ff", "#30d158", "#ff9f0a", "#ff453a", "#bf5af2", "#64d2ff", "#ff375f", "#ffd60a"]


def _icon(color: str) -> QIcon:
    pm = QPixmap(14, 14)
    pm.fill(QColor(color))
    return QIcon(pm)


def _portable(edit: QKeySequenceEdit) -> str:
    return edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)


class CategoryEditDialog(QDialog):
    def __init__(self, others: list[Category], category: Category | None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Catégorie")
        self.setModal(True)
        self.setMinimumWidth(360)
        self.others = others
        self.cat = category
        self.color = category.color if category else random.choice(PASTELS)
        self.result_category: Category | None = None
        self.name = QLineEdit(category.name if category else "")
        self.name.setMaxLength(MAX_NAME_LEN)
        self.name.setPlaceholderText("ex. Vacances")
        self.key = QKeySequenceEdit()
        try:
            self.key.setMaximumSequenceLength(1)
        except AttributeError:
            pass
        used = {o.shortcut for o in others}
        free = next((k for k in "1234567890" if k not in used), "")
        self.key.setKeySequence(QKeySequence(category.shortcut if category else free))
        self.color_btn = GlassButton("Couleur")
        self._paint_color()
        self.color_btn.clicked.connect(self._pick)
        self.err = QLabel("")
        self.err.setObjectName("error")
        self.err.setWordWrap(True)
        form = QFormLayout()
        form.addRow("Nom", self.name)
        form.addRow("Raccourci", self.key)
        form.addRow("Couleur", self.color_btn)
        ok, cancel = GlassButton("Enregistrer"), GlassButton("Annuler")
        ok.set_variant("primary")
        ok.clicked.connect(self._accept)
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.err)
        lay.addLayout(row)

    def _paint_color(self) -> None:
        self.color_btn.setText(f"Couleur  {self.color}")

    def _pick(self) -> None:
        c = QColorDialog.getColor(QColor(self.color), self, "Couleur")
        if c.isValid():
            self.color = c.name()
            self._paint_color()

    def _accept(self) -> None:
        cat = Category(id=self.cat.id if self.cat else Category.new("", "").id, name=self.name.text().strip(),
                       shortcut=_portable(self.key), color=self.color)
        errors = validate_categories([o for o in self.others] + [cat])
        if errors:
            self.err.setText(errors[0])
            return
        self.result_category = cat
        self.accept()


class CategoryManager(QDialog):
    def __init__(self, cfg: ConfigManager, parent=None) -> None:
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("Gérer les catégories")
        self.setModal(True)  # les raccourcis de tri ne peuvent pas agir en arrière-plan
        self.setMinimumSize(460, 520)
        self.cats: list[Category] = cfg.categories()

        self.profiles = GlassCombo(width=200)
        b_newp, b_delp = GlassButton("Nouveau profil"), GlassButton("Supprimer")
        b_newp.clicked.connect(self._new_profile)
        b_delp.clicked.connect(self._del_profile)
        self.profiles.activated.connect(self._switch_profile)
        prow = QHBoxLayout()
        prow.addWidget(QLabel("Profil"))
        prow.addWidget(self.profiles, 1)
        prow.addWidget(b_newp)
        prow.addWidget(b_delp)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _: self._edit())
        b_add, b_edit, b_del = GlassButton("＋ Ajouter"), GlassButton("Renommer / modifier"), GlassButton("Supprimer")
        b_up, b_down = GlassButton("↑"), GlassButton("↓")
        b_del.set_variant("danger")
        b_add.clicked.connect(self._add)
        b_edit.clicked.connect(self._edit)
        b_del.clicked.connect(self._delete)
        b_up.clicked.connect(lambda: self._move(-1))
        b_down.clicked.connect(lambda: self._move(1))
        tools = QHBoxLayout()
        for b in (b_add, b_edit, b_del, b_up, b_down):
            tools.addWidget(b)

        self.err = QLabel("")
        self.err.setObjectName("error")
        self.err.setWordWrap(True)
        save, cancel = GlassButton("Enregistrer"), GlassButton("Annuler")
        save.set_variant("primary")
        save.clicked.connect(self._save)
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(save)

        lay = QVBoxLayout(self)
        lay.addLayout(prow)
        lay.addWidget(self.list, 1)
        lay.addLayout(tools)
        lay.addWidget(self.err)
        lay.addLayout(row)
        self._refresh_profiles()
        self._refresh()

    # ---------- affichage ----------
    def _refresh(self, select: int = -1) -> None:
        self.list.clear()
        for c in self.cats:
            key = QKeySequence(c.shortcut).toString(QKeySequence.SequenceFormat.NativeText) or "?"
            it = QListWidgetItem(_icon(c.color), f"[{key}]   {c.name}")
            self.list.addItem(it)
        if 0 <= select < len(self.cats):
            self.list.setCurrentRow(select)

    def _refresh_profiles(self) -> None:
        self.profiles.clear()
        self.profiles.addItems(self.cfg.profile_names())
        self.profiles.setCurrentText(self.cfg.active_profile)

    def _row(self) -> int:
        return self.list.currentRow()

    # ---------- catégories ----------
    def _add(self) -> None:
        d = CategoryEditDialog(self.cats, None, self)
        if d.exec() and d.result_category:
            d.result_category.id = Category.new("", "").id
            self.cats.append(d.result_category)
            self._refresh(len(self.cats) - 1)

    def _edit(self) -> None:
        r = self._row()
        if r < 0:
            return
        others = [c for i, c in enumerate(self.cats) if i != r]
        d = CategoryEditDialog(others, self.cats[r], self)
        if d.exec() and d.result_category:
            self.cats[r] = d.result_category
            self._refresh(r)

    def _delete(self) -> None:
        r = self._row()
        if r >= 0 and QMessageBox.question(self, "Supprimer", f"Supprimer « {self.cats[r].name} » ?\n"
                                           "(Le dossier et les photos déjà triées ne sont pas touchés.)") \
                == QMessageBox.StandardButton.Yes:
            del self.cats[r]
            self._refresh()

    def _move(self, d: int) -> None:
        r = self._row()
        if 0 <= r < len(self.cats) and 0 <= r + d < len(self.cats):
            self.cats[r], self.cats[r + d] = self.cats[r + d], self.cats[r]
            self._refresh(r + d)

    # ---------- profils ----------
    def _commit(self) -> bool:
        errors = validate_categories(self.cats)
        if errors:
            self.err.setText(errors[0])
            return False
        self.err.setText("")
        self.cfg.set_categories(self.cats)
        return True

    def _switch_profile(self) -> None:
        name = self.profiles.currentText()
        if name == self.cfg.active_profile:
            return
        if not self._commit():
            self.profiles.setCurrentText(self.cfg.active_profile)
            return
        self.cfg.switch_profile(name)
        self.cats = self.cfg.categories()
        self._refresh()

    def _new_profile(self) -> None:
        name, ok = QInputDialog.getText(self, "Nouveau profil", "Nom du profil :")
        if ok and name.strip() and self._commit():
            copy = QMessageBox.question(self, "Nouveau profil", "Copier les catégories du profil actuel ?") \
                == QMessageBox.StandardButton.Yes
            if self.cfg.create_profile(name, copy):
                self.cats = self.cfg.categories()
                self._refresh_profiles()
                self._refresh()
            else:
                self.err.setText("Nom de profil invalide ou déjà utilisé.")

    def _del_profile(self) -> None:
        if len(self.cfg.profile_names()) <= 1:
            self.err.setText("Impossible de supprimer le dernier profil.")
        elif QMessageBox.question(self, "Supprimer", f"Supprimer le profil « {self.cfg.active_profile} » ?") \
                == QMessageBox.StandardButton.Yes:
            self.cfg.delete_profile(self.cfg.active_profile)
            self.cats = self.cfg.categories()
            self._refresh_profiles()
            self._refresh()

    def _save(self) -> None:
        if self._commit():
            self.accept()
