from matplotlib.ticker import MaxNLocator
import matplotlib.pyplot as mtl
import sqlite3
from collections import Counter
import numpy as np

conn = sqlite3.connect("playerData.db")
cursor = conn.cursor()

classes = ["PT", "PTG", "PTE", "PTB", "PTR", "PTI","KK", "KKG", "KKE", "KKB", "KKR", "KKI","FF", "FFG", "FFE", "FFB", "FFR", "FFI","CV", "CVG", "CVE", "CVB", "CVR", "CVI","CC", "CCG", "CCE", "CCB", "CCR", "CCI","BB", "BBG", "BBE", "BBB", "BBR", "BBI","DN", "DNG", "DNE", "DNB", "DNR", "DNI", "Skiff", "Barge", "Installation", "Outpost"]

readiness = ["CRDY", "RDY", "RTB", "DMG", "SAR"]

class_colors = {
    "PT": "#4a0d0d", "PTG": "#825858", "PTE": "#a98c8c", "PTB": "#c4b0b0", "PTR": "#d6c8c8", "PTI": "#e3d9d9",
    "KK": "#4d7d78", "KKG": "#84a5a2", "KKE": "#aac1bf", "KKB": "#c5d4d3", "KKR": "#d7e2e0", "KKI": "#e3ebea",
    "FF": "#e0c400", "FFG": "#ead64f", "FFE": "#f0e386", "FFB": "#f5ecab", "FFR": "#f8f2c5", "FFI": "#faf6d7",
    "CV": "#e0954f", "CVG": "#eab686", "CVE": "#f0cdab", "CVB": "#f5dcc5", "CVR": "#f8e7d7", "CVI": "#faeee4",
    "CC": "#c81e1e", "CCG": "#d96464", "CCE": "#e59494", "CCB": "#edb5b5", "CCR": "#f3cccc", "CCI": "#f6dcdc",
    "BB": "#1d4a8f", "BBG": "#6382b2", "BBE": "#93a9ca", "BBB": "#b5c4da", "BBR": "#ccd6e6", "BBI": "#dce3ee",
    "DN": "#5a1d8f", "DNG": "#8d63b2", "DNE": "#b093ca", "DNB": "#c9b5da", "DNR": "#dacce6", "DNI": "#e5dcee",
	 "Skiff": "#b093ca", "Barge": "#c9b5da", "Installation": "#dacce6", "Outpost": "#e5dcee"}

readiness_colors = {
    "CRDY": "#2e7d32", "RDY": "#66bb6a", "RTB": "#ffca28",
    "DMG": "#e65100", "SAR": "#b71c1c",
}


class Figure:
    def __init__(self):
        cm = 1 / 2.54
        self.fig = mtl.figure(figsize=(64 * cm, 36 * cm))
        self.plot()

    def getData(self):
        faction_rows = []
        player_rows = []

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        table_names = cursor.fetchall()

        for (name,) in table_names:
            cursor.execute(f'SELECT Grid_Core, Status, Location FROM "{name}"')
            rows = cursor.fetchall()

            if name == "Faction":
                faction_rows.extend(rows)
            else:
                player_rows.extend(rows)

        return faction_rows, player_rows

    def plot_stacked(self, ax, rows, groups, colors, key_index, title):
        locations = sorted({loc for row in rows if (loc := row[2]) is not None})
        if not locations:
            ax.set_title(title)
            return

        x = np.arange(len(locations))  # numeric positions instead of raw strings

        counts = {g: Counter() for g in groups}
        for row in rows:
            key = row[key_index]
            loc = row[2]
            if key in counts:
                counts[key][loc] += 1

        bottoms = [0] * len(locations)
        for g in groups:
            heights = [counts[g].get(loc, 0) for loc in locations]
            bars = ax.bar(x, heights, bottom=bottoms, width=0.6,
                        color=colors.get(g, "#888888"), label=g)

            for bar, h in zip(bars, heights):
                if h > 0:
                    ax.text(bar.get_x() + bar.get_width() / 2,
                            bar.get_y() + h / 2,
                            str(h), ha="center", va="center",
                            fontsize=8, fontweight="bold", color="black")

            bottoms = [b + h for b, h in zip(bottoms, heights)]

        for x_pos, total in zip(x, bottoms):
            if total > 0:
                ax.text(x_pos, total + max(bottoms) * 0.02, str(total),
                        ha="center", va="bottom", fontsize=9, color="gray")
            else:
                ax.text(x_pos, 0.1, "0", ha="center", va="bottom",
                        fontsize=9, color="#a67c00", fontweight="bold")

        ax.set_xticks(x)
        ax.set_xticklabels(locations)
        ax.set_xlim(-0.5, len(locations) - 0.5)  # explicit padding so first/last bars aren't clipped

        ax.set_title(title)
        ax.set_ylabel("Vessel Count")
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_ylim(0,16)
        ax.legend(fontsize=6, ncol=2, loc="upper right")

    def plot(self):
        faction_rows, player_rows = self.getData()

        ax1 = self.fig.add_subplot(221)
        self.plot_stacked(ax1, faction_rows, classes, class_colors, 0, "Faction Fleet Breakdown")
        
        ax2 = self.fig.add_subplot(222)
        self.plot_stacked(ax2, faction_rows, readiness, readiness_colors, 1, "Faction Fleet Readiness")

        ax3 = self.fig.add_subplot(223)
        self.plot_stacked(ax3, player_rows, classes, class_colors, 0, "Personal Vessel Breakdown")
        
        ax4 = self.fig.add_subplot(224)
        self.plot_stacked(ax4, player_rows, readiness, readiness_colors, 1, "Personal Vessel Readiness")

        self.fig.tight_layout()
        mtl.savefig(fname="view.png", bbox_inches="tight")