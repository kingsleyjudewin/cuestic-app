import os
import io
import random
import base64
import logging
from typing import Dict, Any, List, Optional, Tuple
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

logger = logging.getLogger(__name__)

# Standard ABET / NBA Programme Outcomes with full questions and statements
PO_FULL_DEFINITIONS = {
    "PO1": {
        "title": "Engineering Knowledge",
        "question": "PO1: How effectively did the activity reinforce fundamental engineering knowledge and principles?",
        "focus": "fundamental engineering concepts, analytical problem solving, and core subject grounding",
    },
    "PO2": {
        "title": "Problem Analysis",
        "question": "PO2: Did the activity enhance participants' ability to identify, formulate, and analyze complex engineering problems?",
        "focus": "systematic problem analysis, literature appraisal, and structured reasoning",
    },
    "PO3": {
        "title": "Design/Development of Solutions",
        "question": "PO3: How well did the activity support the design and development of engineering solutions to practical challenges?",
        "focus": "creative system design, technical prototyping, and practical solution synthesis",
    },
    "PO4": {
        "title": "Conduct Investigations of Complex Problems",
        "question": "PO4: Did the activity provide experience in conducting investigations, experiments, or diagnostic assessments?",
        "focus": "experimental methodologies, data interpretation, and evidentiary deductions",
    },
    "PO5": {
        "title": "Modern Tool Usage",
        "question": "PO5: How effectively did the session introduce or apply modern engineering tools, software, or simulation platforms?",
        "focus": "contemporary software tools, simulation packages, and engineering tool adaptation",
    },
    "PO6": {
        "title": "The Engineer and Society",
        "question": "PO6: Did the activity highlight the societal, safety, legal, and cultural responsibilities of engineering practice?",
        "focus": "societal context, public welfare, and professional responsibility",
    },
    "PO7": {
        "title": "Environment and Sustainability",
        "question": "PO7: Did the activity address environmental considerations and sustainable engineering practices?",
        "focus": "environmental awareness, sustainability standards, and resource optimization",
    },
    "PO8": {
        "title": "Ethics",
        "question": "PO8: How effectively did the activity emphasize professional ethics, integrity, and ethical conduct?",
        "focus": "academic honesty, engineering ethics, and responsible professional standards",
    },
    "PO9": {
        "title": "Individual and Team Work",
        "question": "PO9: Did the activity foster collaborative teamwork, task delegation, and diverse peer interactions?",
        "focus": "cross-functional teamwork, cooperative problem solving, and peer leadership",
    },
    "PO10": {
        "title": "Communication",
        "question": "PO10: How well did the activity facilitate clear technical communication, documentation, and presentation?",
        "focus": "technical articulation, presentation clarity, and collaborative documentation",
    },
    "PO11": {
        "title": "Project Management and Finance",
        "question": "PO11: Did the activity incorporate elements of task management, resource planning, or project execution?",
        "focus": "agile execution, timeline management, and organizational coordination",
    },
    "PO12": {
        "title": "Life-long Learning",
        "question": "PO12: Did the activity inspire self-directed curiosity and lifelong engagement with emerging technological domains?",
        "focus": "autonomous learning motivation, forward-looking exploration, and career-long curiosity",
    },
}

FEEDBACK_COLORS = {
    "Excellent": "#109618",     # Google Green
    "Very Good": "#FF9900",     # Google Orange
    "Fair": "#3366CC",          # Google Blue
    "Satisfactory": "#DC3912",  # Google Red
}

CLASS_COHORTS = [
    "4BTELCS",
    "4BTEC",
    "5BTELCS",
    "5BTEC",
    "6BTELCS",
    "6BTEC",
    "8BTELCS",
    "8BTEC",
]

CLASS_COLORS = [
    "#4285F4",  # Blue
    "#EA4335",  # Red
    "#FBBC05",  # Yellow
    "#34A853",  # Green
    "#FF6D01",  # Orange
    "#46BDC6",  # Cyan
    "#7BAAF7",  # Light Blue
    "#BA68C8",  # Purple
]


class SimulationService:
    """
    Simulates participant attendance distributions, Impact Analysis questions/answers,
    and 12 Programme Outcome (PO1-PO12) feedback pie charts with full Google Forms visual styling.
    """

    @classmethod
    def generate_simulated_impact_analysis(
        cls,
        activity_title: str = "Department Activity",
        participant_count: Optional[int] = None,
        seed: Optional[int] = None,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate simulated participant count (200-230), class distribution across the 8 cohorts,
        participation narrative, and answers to all 12 Impact Analysis questions.
        """
        rng = random.Random(seed)

        # 1. Simulated participant count (between 200 and 230)
        total_participants = participant_count if (participant_count and 200 <= participant_count <= 250) else rng.randint(200, 230)

        # 2. Simulated class distribution across 8 classes:
        # 4BTELCS, 4BTEC, 5BTELCS, 5BTEC, 6BTELCS, 6BTEC, 8BTELCS, 8BTEC
        weights = [0.08, 0.12, 0.07, 0.13, 0.23, 0.09, 0.14, 0.14]
        jittered = [max(0.04, w + rng.uniform(-0.02, 0.02)) for w in weights]
        s = sum(jittered)
        norm_weights = [w / s for w in jittered]

        counts = [int(round(w * total_participants)) for w in norm_weights]
        diff = total_participants - sum(counts)
        counts[4] += diff  # reconcile difference on largest cohort (6BTELCS)

        class_dist_list = []
        for c_name, cnt in zip(CLASS_COHORTS, counts):
            pct = round((cnt / total_participants) * 100.0, 1)
            class_dist_list.append({
                "class_name": c_name,
                "count": cnt,
                "percentage": pct,
            })

        # 3. Generate Google Forms style Class pie chart
        chart_bytes, chart_b64 = cls.generate_class_pie_chart(class_dist_list, output_dir=output_dir)

        # 4. Generate Participation Summary & Narrative Interpretation
        classes_str = ", ".join(CLASS_COHORTS)
        top_cohort = max(class_dist_list, key=lambda x: x["count"])
        narrative = (
            f"[Simulated Data] The activity recorded a simulated participation of {total_participants} students "
            f"across academic cohorts ({classes_str}) within the Department of Electronics and Communication Engineering. "
            f"The largest representation was observed from {top_cohort['class_name']} ({top_cohort['count']} participants, {top_cohort['percentage']}%), "
            f"providing comprehensive cross-year collaboration and multi-cohort peer engagement."
        )

        # 5. Generate Answers to all 12 Impact Analysis Questions
        questions = cls._generate_12_impact_questions(total_participants, class_dist_list, activity_title)

        return {
            "mode": "simulation",
            "is_simulated": True,
            "seed": seed,
            "participant_count": total_participants,
            "class_distribution": class_dist_list,
            "class_chart_base64": chart_b64,
            "narrative": narrative,
            "questions": questions,
        }

    @classmethod
    def generate_class_pie_chart(
        cls,
        class_distribution: List[Dict[str, Any]],
        output_dir: Optional[str] = None,
    ) -> Tuple[bytes, str]:
        """Generate high-res Google Forms style Class pie chart matching Pasted image.png."""
        labels = [item["class_name"] for item in class_distribution if item["count"] > 0]
        counts = [item["count"] for item in class_distribution if item["count"] > 0]
        total = sum(counts)

        fig, ax = plt.subplots(figsize=(6.4, 3.9), dpi=300, facecolor="#ffffff")
        ax.set_facecolor("#ffffff")

        slice_colors = [CLASS_COLORS[i % len(CLASS_COLORS)] for i in range(len(labels))]
        wedges, texts, autotexts = ax.pie(
            counts,
            colors=slice_colors,
            autopct=lambda pct: f"{pct:.1f}%" if pct >= 1.0 else "",
            startangle=140,
            textprops=dict(color="#ffffff", weight="bold", fontsize=9),
            pctdistance=0.72,
            wedgeprops=dict(edgecolor="#ffffff", linewidth=1.5),
        )

        legend_handles = [
            Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor=slice_colors[i],
                markeredgecolor="none",
                markersize=8,
            )
            for i in range(len(labels))
        ]
        ax.legend(
            handles=legend_handles,
            labels=labels,
            loc="center left",
            bbox_to_anchor=(1.02, 0.5),
            frameon=False,
            fontsize=9,
            handletextpad=0.6,
        )

        ax.set_title(f"Class Distribution\n{total} responses", fontsize=11, weight="bold", pad=12, loc="left", color="#202124")

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=300, facecolor="#ffffff")
        plt.close(fig)

        raw_bytes = buf.getvalue()
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            fp = os.path.join(output_dir, "chart_simulated_class_distribution.png")
            with open(fp, "wb") as f:
                f.write(raw_bytes)

        b64 = f"data:image/png;base64,{base64.b64encode(raw_bytes).decode('ascii')}"
        return raw_bytes, b64

    @classmethod
    def _generate_12_impact_questions(
        cls,
        participant_count: int,
        class_dist: List[Dict[str, Any]],
        activity_title: str
    ) -> List[Dict[str, str]]:
        """Draft 12 meaningful, professional answers tailored to the simulated metrics."""
        classes_str = ", ".join([f"{c['class_name']} ({c['count']})" for c in class_dist])
        clean_title = activity_title.replace("Activity Report", "").strip() or "the activity"

        return [
            {
                "question": "1. How effectively did the activity address its stated objectives?",
                "answer": f"[Simulated] The session comprehensively met its curricular targets by immersing {clean_title} participants in structured technical scenarios and practical methodologies."
            },
            {
                "question": "2. How many verified participants attended the activity?",
                "answer": f"[Simulated] A total of {participant_count} simulated attendees were recorded across the session."
            },
            {
                "question": "3. Which academic classes were represented?",
                "answer": f"[Simulated] Multi-cohort representation was documented across: {classes_str}."
            },
            {
                "question": "4. Did the activity provide exposure to the intended technical subject?",
                "answer": "[Simulated] Yes, participants engaged with domain-specific core engineering concepts and hands-on analytical problem-solving modules."
            },
            {
                "question": "5. Did the activity provide opportunities for knowledge exchange?",
                "answer": "[Simulated] Yes, interactive problem-solving rounds and group discussions encouraged cross-cohort technical exchange."
            },
            {
                "question": "6. Did the activity encourage student engagement?",
                "answer": "[Simulated] Active student participation was evidenced through high task completion rates and competitive execution."
            },
            {
                "question": "7. Did the activity support practical or research-oriented learning?",
                "answer": "[Simulated] Yes, students applied theoretical foundations to empirical problem scenarios and real-world system modeling."
            },
            {
                "question": "8. Did the activity facilitate interaction with speakers or experts?",
                "answer": "[Simulated] Faculty coordinators and designated student leads actively provided technical mentorship throughout each segment."
            },
            {
                "question": "9. Did the activity encourage interdisciplinary collaboration?",
                "answer": "[Simulated] Team challenges fostered collaborative dynamics across Electronics and Communication Engineering cohorts."
            },
            {
                "question": "10. Did the activity provide insights into relevant industry or research practices?",
                "answer": "[Simulated] The workflow mirrored industry standards, emphasizing agile coordination, structured testing, and rapid verification."
            },
            {
                "question": "11. What key outcomes were documented during the activity?",
                "answer": "[Simulated] Measurable outcomes include successful challenge submissions, enhanced technical proficiency, and high attainment across Programme Outcomes."
            },
            {
                "question": "12. What follow-up opportunities or improvements were identified?",
                "answer": "[Simulated] Organizers noted opportunities for advanced follow-on workshops and expanded hardware/software laboratory allocations."
            },
        ]

    @classmethod
    def generate_simulated_feedback_analysis(
        cls,
        participant_count: int = 224,
        activity_title: str = "Department Activity",
        seed: Optional[int] = None,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate all 12 Programme Outcome (PO1-PO12) feedback pie charts,
        individual distribution tables, overall summary table, and written interpretations.
        """
        rng = random.Random(seed)
        po_results = {}
        summary_table_rows = []

        for po_idx in range(1, 13):
            po_id = f"PO{po_idx}"
            po_meta = PO_FULL_DEFINITIONS[po_id]
            po_title = po_meta["title"]
            po_question = po_meta["question"]

            # Generate random integer allocation:
            # Excellent: 45–60%
            # Very Good: 30–45%
            # Fair: 3–12%
            # Satisfactory: 0–5%
            p_exc = rng.uniform(0.46, 0.58)
            p_vg = rng.uniform(0.31, 0.43)
            p_fair = rng.uniform(0.04, 0.10)
            p_sat = rng.uniform(0.01, 0.04)

            # Normalize to 1.0
            sum_p = p_exc + p_vg + p_fair + p_sat
            p_exc /= sum_p
            p_vg /= sum_p
            p_fair /= sum_p
            p_sat /= sum_p

            c_exc = int(round(p_exc * participant_count))
            c_vg = int(round(p_vg * participant_count))
            c_fair = int(round(p_fair * participant_count))
            c_sat = participant_count - (c_exc + c_vg + c_fair)

            if c_sat < 0:
                c_vg += c_sat
                c_sat = 0
            if c_fair < 0:
                c_fair = 0

            counts = {
                "Excellent": c_exc,
                "Very Good": c_vg,
                "Fair": c_fair,
                "Satisfactory": c_sat,
            }

            percentages = {
                cat: round((cnt / float(participant_count)) * 100.0, 1)
                for cat, cnt in counts.items()
            }

            # Generate Google Forms style Pie Chart
            chart_bytes, chart_b64 = cls._generate_single_po_chart(
                po_id=po_id,
                po_title=po_title,
                po_question=po_question,
                counts=counts,
                percentages=percentages,
                total=participant_count,
                output_dir=output_dir,
            )

            # Generate individual written interpretation
            interpretation = cls._draft_po_interpretation(
                po_id=po_id,
                po_title=po_title,
                counts=counts,
                percentages=percentages,
                total=participant_count,
            )

            po_results[po_id] = {
                "po_id": po_id,
                "po_title": po_title,
                "po_question": po_question,
                "total_responses": participant_count,
                "counts": counts,
                "percentages": percentages,
                "positive_percentage": round(percentages["Excellent"] + percentages["Very Good"], 1),
                "chart_base64": chart_b64,
                "interpretation": interpretation,
                "is_simulated": True,
            }

            summary_table_rows.append({
                "po": po_id,
                "po_title": po_title,
                "excellent": c_exc,
                "very_good": c_vg,
                "fair": c_fair,
                "satisfactory": c_sat,
                "total": participant_count,
                "positive_pct": round(percentages["Excellent"] + percentages["Very Good"], 1),
            })

        overall_interpretation = (
            f"[Simulated Data] A simulated feedback evaluation across all twelve Programme Outcomes (PO1–PO12) "
            f"was conducted with {participant_count} respondents. The simulated feedback demonstrates robust overall "
            f"student attainment, with over 80% combined 'Excellent' and 'Very Good' satisfaction across technical, "
            f"practical, and professional domains."
        )

        return {
            "mode": "simulation",
            "is_simulated": True,
            "seed": seed,
            "total_responses": participant_count,
            "summary_table": summary_table_rows,
            "po_results": po_results,
            "overall_interpretation": overall_interpretation,
        }

    @classmethod
    def generate_single_simulated_po(
        cls,
        po_id: str,
        participant_count: int = 224,
        seed: Optional[int] = None,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate simulation data and pie chart for a single Programme Outcome."""
        if po_id not in PO_FULL_DEFINITIONS:
            po_id = "PO1"
        rng = random.Random(seed)
        po_meta = PO_FULL_DEFINITIONS[po_id]
        po_title = po_meta["title"]
        po_question = po_meta["question"]

        p_exc = rng.uniform(0.46, 0.58)
        p_vg = rng.uniform(0.31, 0.43)
        p_fair = rng.uniform(0.04, 0.10)
        p_sat = rng.uniform(0.01, 0.04)

        sum_p = p_exc + p_vg + p_fair + p_sat
        p_exc /= sum_p
        p_vg /= sum_p
        p_fair /= sum_p
        p_sat /= sum_p

        c_exc = int(round(p_exc * participant_count))
        c_vg = int(round(p_vg * participant_count))
        c_fair = int(round(p_fair * participant_count))
        c_sat = participant_count - (c_exc + c_vg + c_fair)
        if c_sat < 0:
            c_vg += c_sat
            c_sat = 0
        if c_fair < 0:
            c_fair = 0

        counts = {
            "Excellent": c_exc,
            "Very Good": c_vg,
            "Fair": c_fair,
            "Satisfactory": c_sat,
        }
        percentages = {
            cat: round((cnt / float(participant_count)) * 100.0, 1)
            for cat, cnt in counts.items()
        }

        chart_bytes, chart_b64 = cls._generate_single_po_chart(
            po_id=po_id,
            po_title=po_title,
            po_question=po_question,
            counts=counts,
            percentages=percentages,
            total=participant_count,
            output_dir=output_dir,
        )

        interpretation = cls._draft_po_interpretation(
            po_id=po_id,
            po_title=po_title,
            counts=counts,
            percentages=percentages,
            total=participant_count,
        )

        return {
            "po_id": po_id,
            "po_title": po_title,
            "po_question": po_question,
            "total_responses": participant_count,
            "counts": counts,
            "percentages": percentages,
            "positive_percentage": round(percentages["Excellent"] + percentages["Very Good"], 1),
            "chart_base64": chart_b64,
            "interpretation": interpretation,
            "is_simulated": True,
        }

    @classmethod
    def _generate_single_po_chart(
        cls,
        po_id: str,
        po_title: str,
        po_question: str,
        counts: Dict[str, int],
        percentages: Dict[str, float],
        total: int,
        output_dir: Optional[str] = None,
    ) -> Tuple[bytes, str]:
        """
        Render a Google Forms visual style pie chart:
        - White background.
        - Circular pie chart.
        - White borders separating slices.
        - Percentage labels inside slices.
        - White bold percentage text.
        - Legend on right with rating, count, and %.
        - Readable PO title above chart.
        """
        categories = ["Excellent", "Very Good", "Fair", "Satisfactory"]
        slice_counts = [counts[c] for c in categories]
        slice_colors = [FEEDBACK_COLORS[c] for c in categories]

        fig, ax = plt.subplots(figsize=(6.4, 3.8), dpi=300, facecolor="#ffffff")
        ax.set_facecolor("#ffffff")

        wedges, texts, autotexts = ax.pie(
            slice_counts,
            colors=slice_colors,
            autopct=lambda pct: f"{pct:.1f}%" if pct >= 1.0 else "",
            startangle=140,
            textprops=dict(color="#ffffff", weight="bold", fontsize=9),
            pctdistance=0.72,
            wedgeprops=dict(edgecolor="#ffffff", linewidth=1.5),
        )

        legend_categories = ["Fair", "Satisfactory", "Very Good", "Excellent"]
        legend_handles = [
            Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor=FEEDBACK_COLORS[c],
                markeredgecolor="none",
                markersize=7,
                linestyle="None",
            )
            for c in legend_categories
        ]
        ax.legend(
            handles=legend_handles,
            labels=legend_categories,
            loc="center left",
            bbox_to_anchor=(1.02, 0.5),
            frameon=False,
            fontsize=9,
            handletextpad=0.6,
        )

        chart_heading = f"{po_id}: {po_title}\n{total} responses"
        ax.set_title(chart_heading, fontsize=11, weight="bold", pad=12, loc="left", color="#202124")

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=300, facecolor="#ffffff")
        plt.close(fig)

        raw_bytes = buf.getvalue()
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            fp = os.path.join(output_dir, f"chart_simulated_{po_id.lower()}.png")
            with open(fp, "wb") as f:
                f.write(raw_bytes)

        b64 = f"data:image/png;base64,{base64.b64encode(raw_bytes).decode('ascii')}"
        return raw_bytes, b64

    @classmethod
    def _draft_po_interpretation(
        cls,
        po_id: str,
        po_title: str,
        counts: Dict[str, int],
        percentages: Dict[str, float],
        total: int,
    ) -> str:
        """Draft a professional, non-repetitive written interpretation based on actual simulated numbers."""
        exc_pct = percentages["Excellent"]
        vg_pct = percentages["Very Good"]
        fair_pct = percentages["Fair"]
        sat_pct = percentages["Satisfactory"]
        pos_pct = round(exc_pct + vg_pct, 1)

        templates = [
            (
                f"[Simulated Data] The simulated feedback for {po_id} ({po_title}) indicates that {exc_pct}% of respondents "
                f"rated this outcome as Excellent ({counts['Excellent']} responses), while {vg_pct}% rated it Very Good ({counts['Very Good']} responses). "
                f"A combined {round(fair_pct + sat_pct, 1)}% evaluated it as Fair or Satisfactory. "
                f"Overall, with {pos_pct}% positive ratings, the simulated distribution demonstrates strong curricular attainment."
            ),
            (
                f"[Simulated Data] For {po_id}: {po_title}, {counts['Excellent']} participants ({exc_pct}%) recorded an Excellent rating, "
                f"complemented by {vg_pct}% in the Very Good category. Fair ratings accounted for {fair_pct}%, with Satisfactory comprising {sat_pct}%. "
                f"This simulated profile reflects commendable student receptivity and solid alignment with departmental learning targets."
            ),
            (
                f"[Simulated Data] Participant feedback simulation for {po_id} shows that {exc_pct}% achieved Excellent satisfaction, "
                f"accompanied by {vg_pct}% Very Good responses out of {total} total simulated entries. "
                f"Minor proportions selected Fair ({fair_pct}%) and Satisfactory ({sat_pct}%), confirming a distinctively favorable outcome perception."
            ),
        ]

        # Use deterministic variant per PO so adjacent POs do not sound identical
        variant_idx = int(po_id.replace("PO", "")) % len(templates)
        return templates[variant_idx]
