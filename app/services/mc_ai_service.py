import os
import re
import json
import logging
from typing import Optional, Dict, List, Tuple
from app.services.ai_service import AIService, AIProviderNotConfiguredError
from app.utils.errors import ValidationError

logger = logging.getLogger(__name__)

SYSTEM_MC_INSTRUCTION = """
You are an expert Master of Ceremonies (MC) and Event Hosting Scriptwriter for university events at CHRIST (Deemed to be University), Bangalore (Department of Electronics and Communication Engineering / CUestIC Club / IEEE Student Branch).

Your role is to write polished, natural, captivating, and stage-ready hosting scripts for anchors based on actual university and department protocols.

CRITICAL HOSTING & FORMATTING GUIDELINES (Modeled directly after official IEEE & Valedictory functions):
1. ANCHOR DIALOGUE & TURNS:
   - Clearly assign and label each spoken line with the anchor's tag (e.g. '(MC 1 - Merrick):' or '(MC 2 - Afra):' or '(Vishrutha):' or '(Abhi):').
   - Keep dialogue conversational, courteous, dignified, and stage-ready.
   - Maintain alternating flow between anchors.

2. STAGE DIRECTIONS:
   - Enclose every physical or visual stage instruction strictly in square brackets, e.g.:
     * [Pause for applause as speaker takes the stage]
     * [MC 1 steps to podium, smiling warmly; waits for silence]
     * [Both anchors turn gracefully towards the dais]
     * [Music fades softly as MC begins speaking]
     * [Dignitaries step forward to ceremonial oil lamp]
     * [Request all heads to remain on stage for official group photograph]

3. FACTUAL FIDELITY & ZERO HALLUCINATIONS (CRITICAL):
   - Never invent or assume qualifications, scientific paper titles, awards, institutional positions, or dignitary designations.
   - If speaker biography is supplied (e.g., degrees, institutions, Stanford top 2% list, publications count), integrate it faithfully.
   - For Prize Distributions, announce exact competition names, categories, and positions (1st, 2nd, 3rd) without changing winner names.
   - For Dignitary Welcomes, respect the formal university hierarchy: Director, Assistant Director, Dean, Associate Dean, Head of Department, Branch Counsellors, Faculty Coordinators. Include '(in absentia)' if specified.
   - If details are omitted, use clear bracketed placeholders like `[Insert Presenter Name]` or `[Insert Chief Guest Title]`.

4. CONTINUOUS FLOW & NATURAL TRANSITIONS:
   - Acknowledge previous speakers/events respectfully (e.g., "Thank you, ma'am, for those encouraging words that have beautifully set the tone for today's technical journey...").
   - Vary appreciation phrases and avoid repetitive catchphrases like "put your hands together" every time.
   - Build natural anticipation for upcoming sessions and presentations.
"""


class MCAssistantService:
    """Service providing AI-powered hosting script drafting, section expansion, and stage direction generation."""

    @classmethod
    def generate_segment_dialogue(
        cls,
        segment_type: str,
        event_info: dict,
        segment_info: dict,
        prev_segment: Optional[dict] = None,
        next_segment: Optional[dict] = None,
        action: str = "generate",
        current_dialogue: Optional[str] = None,
        current_stage_directions: Optional[str] = None,
        user_prompt: Optional[str] = None,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Dict:
        """
        Generate or refine an individual segment's dialogue and stage directions with rich contextual awareness.
        Understands neighboring segments for natural transitions.
        """
        title = event_info.get("event_name") or event_info.get("title") or "Department Event"
        dept = event_info.get("organizing_department") or "Department of Electronics and Communication Engineering"
        club = event_info.get("organizing_club") or "CUestIC & IEEE Student Branch"
        venue = event_info.get("venue") or "Campus Auditorium"
        tone = event_info.get("tone") or "Formal"
        anchors = event_info.get("anchors") or [{"name": "Anchor 1"}, {"name": "Anchor 2"}]
        anchor_names = [a.get("name", f"Anchor {i+1}") for i, a in enumerate(anchors)]

        seg_title = segment_info.get("title") or "Programme Segment"
        assigned_mc = segment_info.get("assigned_mc") or (anchor_names[0] if anchor_names else "MC 1")
        input_data = segment_info.get("input_data") or {}

        # Contextual summary of previous and next segments for seamless stage transitions
        prev_context = ""
        if prev_segment:
            prev_context = f"- Previous Segment: '{prev_segment.get('title')}' (Assigned to: {prev_segment.get('assigned_mc', 'MC')})\n"
            if prev_segment.get("generated_dialogue"):
                prev_snippet = prev_segment["generated_dialogue"][:200]
                prev_context += f"  Snippet of previous segment ending: \"{prev_snippet}...\"\n"

        next_context = ""
        if next_segment:
            next_context = f"- Next Segment: '{next_segment.get('title')}' (Assigned to: {next_segment.get('assigned_mc', 'MC')})\n"

        prompt = f"""
You are crafting the MC dialogue and stage directions for ONE specific programme segment in an official university event.

=== EVENT CONTEXT ===
- Event Title: {title}
- Organizing Department: {dept}
- Organizing Club / Chapter: {club}
- Venue: {venue}
- Tone: {tone}
- MC Anchors on Stage: {', '.join(anchor_names)}
- MC Assigned to this Segment: {assigned_mc}

=== SEGMENT DETAILS ===
- Segment Type: {segment_type}
- Segment Title: {seg_title}
- Segment Inputs & Structured Data:
{json.dumps(input_data, indent=2)}

=== PROGRAMME FLOW CONTEXT ===
{prev_context}
{next_context}

=== ACTION REQUIRED ===
Action: {action.upper()}
User Custom Guidance / Instruction: {user_prompt or 'Generate complete stage dialogue and bracketed stage directions matching university event standards.'}
Current Dialogue (if refining): {current_dialogue or 'None'}
Current Stage Directions (if refining): {current_stage_directions or 'None'}

=== SEGMENT SPECIFIC WRITING GUIDELINES ===
"""
        # Specific guidelines based on segment type
        if segment_type == "opening_greeting":
            prompt += """
- Start with a courteous time-of-day greeting.
- Introduce the MCs by name (e.g., 'I am Merrick Dias, and alongside my co-host Qurrath Ul Ain, we are honoured to be your MCs for the day...').
- Welcome the audience on behalf of the department and club.
- State the purpose, theme, and significance of the event.
- Provide a smooth opening transition.
"""
        elif segment_type == "pre_event_announcement":
            prompt += """
- Politely remind the audience to switch mobile devices to silent mode.
- Request everyone to be seated and maintain decorum throughout the ceremony.
- Mention that the esteemed dignitaries will be arriving shortly.
- Express appreciation for their patience and cooperation.
"""
        elif segment_type == "dignitary_introduction":
            prompt += """
- Formally acknowledge the dignitaries strictly in the order provided in the input data.
- Mention management (Director, Assistant Director, Dean, Associate Dean, HOD, Coordinators).
- If any dignitary is absent, include '(in absentia)'.
- Do not fabricate titles. Use exact designations provided.
"""
        elif segment_type == "welcome_address":
            prompt += """
- Introduce the person delivering the welcome address with their exact designation and department.
- Invite them to the stage with a warm round of applause.
- Provide a post-address acknowledgement thanking them for their encouraging words and for setting the tone.
"""
        elif segment_type == "speaker_introduction":
            prompt += """
- Seamlessly transition into the technical session.
- Present the speaker's distinguished career, degrees, academic institutions, and professional roles.
- Mention awards, publications, and Stanford top 2% list or IEEE roles if provided in the input data.
- Introduce the presentation topic and invite the speaker to the podium.
- Include a sapling or memento presentation cue before or after the talk.
- Add an applause instruction.
"""
        elif segment_type == "prize_distribution":
            prompt += """
- Build excitement and congratulate all participants on their hard work.
- Announce competition categories and winners in exact order (1st, 2nd, 3rd place).
- Clearly mention winner names and team names without alteration.
- Invite the designated faculty or dignitary to present certificates, trophies, or cash prizes.
- Conclude with applause and congratulations.
"""
        elif segment_type == "badge_distribution":
            prompt += """
- Recognize student leadership (Heads and Vice-Heads of student wings).
- Invite the dignitary on stage to do the honours of presenting the badges.
- Call each head and vice-head individually by title and name (e.g. 'Rithvik, Head of Volunteering Body — please come forward...').
- Request all leaders to remain on stage together for a commemorative group photograph.
"""
        elif segment_type == "event_report":
            prompt += """
- Highlight the importance of summarizing the journey, efforts, and milestones.
- Invite the Event Head or Convenor by name and designation to present the comprehensive report.
- Post-report thank you acknowledging their leadership.
"""
        elif segment_type == "memento_presentation":
            prompt += """
- Express heartfelt gratitude to the guest for their profound insights and time.
- Call upon the designated presenter to present the memento/sapling as a token of reverence and appreciation.
- Pause for photograph on stage.
"""
        elif segment_type == "vote_of_thanks":
            prompt += """
- Invite the designated faculty member or convenor to deliver the formal vote of thanks.
- If generating the vote of thanks speech directly: acknowledge Management, Director, Dean, HOD, Guest Speakers, Coordinators, Student MCs, Volunteers, Tech Support, Media Team, and the student body.
"""
        elif segment_type == "anthem_closing":
            prompt += """
- Request the entire gathering to please rise for the University Anthem or National Anthem.
- Stage direction for standing at attention while anthem plays.
"""
        elif segment_type == "feedback_announcements":
            prompt += """
- Instruct students to scan the QR code displayed on the screen for event feedback and certificate dispatch.
- Announce refreshments/tea location outside.
- Announce resumption of classes or period attendance procedures clearly.
"""

        prompt += """
OUTPUT REQUIREMENTS:
Return your response as a valid JSON object matching this exact structure:
{
  "dialogue": "Exact spoken words for the assigned MC with speaker prefix, e.g. (MC 1 - Merrick): Good morning everyone...",
  "stage_directions": "Bracketed stage instructions, e.g. [MC 1 pauses for silence; smiles warmly at the audience]",
  "transition_note": "Brief explanation of how this connects to preceding and succeeding segments."
}

Return ONLY the raw JSON object. Do not wrap in markdown fences.
"""

        try:
            raw_text, resolved_provider, resolved_model = AIService.generate_with_resilient_fallback(
                prompt=prompt,
                system_instruction=SYSTEM_MC_INSTRUCTION,
                provider_name=provider_name,
                model_name=model_name,
            )

            cleaned = raw_text.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

            parsed = {}
            try:
                parsed = json.loads(cleaned)
            except Exception:
                m = re.search(r"\{.*\}", cleaned, re.DOTALL)
                if m:
                    parsed = json.loads(m.group(0))

            dialogue = parsed.get("dialogue") or raw_text
            stage_dirs = parsed.get("stage_directions") or segment_info.get("default_stage_directions") or "[MC takes the stage]"

            return {
                "dialogue": dialogue,
                "stage_directions": stage_dirs,
                "transition_note": parsed.get("transition_note", ""),
                "provider": resolved_provider,
                "model": resolved_model,
            }
        except Exception as e:
            logger.warning("AI generation failed, applying rule-based generator: %s", e)
            return cls._generate_fallback_segment(segment_type, event_info, segment_info)

    @classmethod
    def _generate_fallback_segment(cls, segment_type: str, event_info: dict, segment_info: dict) -> Dict:
        """Deterministic, high-quality rule-based fallback adhering strictly to university protocol."""
        title = event_info.get("event_name") or event_info.get("title") or "Department Event"
        dept = event_info.get("organizing_department") or "Department of Electronics and Communication Engineering"
        club = event_info.get("organizing_club") or "CUestIC & IEEE Student Branch"
        anchors = event_info.get("anchors") or [{"name": "Anchor 1"}, {"name": "Anchor 2"}]
        assigned_mc = segment_info.get("assigned_mc") or anchors[0].get("name", "MC 1")
        co_mc = anchors[1].get("name", "Co-Host") if len(anchors) > 1 else "Co-Host"
        data = segment_info.get("input_data") or {}

        if segment_type == "pre_event_announcement":
            dialogue = f"({assigned_mc}): Good morning, everyone. We request all of you to kindly switch your mobile phones to silent mode and maintain decorum throughout the ceremony. We are expecting our esteemed dignitaries to arrive shortly. We appreciate your patience and cooperation."
            stage_dirs = f"[{assigned_mc} addresses the hall with clarity from podium; pauses for room silence]"

        elif segment_type == "opening_greeting":
            dialogue = f"({assigned_mc}): A very warm and pleasant morning to everyone present here today. I am {assigned_mc}, and alongside my co-host {co_mc}, we are honoured to be your MCs for {title}. On behalf of the {dept} and {club}, it is our absolute privilege to welcome you all to this edition of today's gathering."
            stage_dirs = f"[{assigned_mc} smiles warmly and gestures towards audience; co-host nods in agreement]"

        elif segment_type == "dignitary_introduction":
            dignitaries = data.get("dignitaries") or []
            if dignitaries:
                names_str = ", ".join([f"{d.get('name')} ({d.get('designation', '')})" for d in dignitaries])
                dialogue = f"({assigned_mc}): We extend our heartfelt welcome to our distinguished dignitaries on stage: {names_str}. We warmly welcome all our respected faculty members, coordinators, and dear students."
            else:
                dialogue = f"({assigned_mc}): On behalf of {dept}, we extend our sincere reverence and welcome to our management, Director, Dean, Head of Department, faculty coordinators, and all our dear students gathered here today."
            stage_dirs = "[Gestures respectfully towards the dignitaries seated on the dais]"

        elif segment_type == "welcome_address":
            speaker = data.get("speaker_name") or "Head of Department"
            desig = data.get("designation") or "Head of Department"
            dialogue = f"({assigned_mc}): To officially set the tone for today's event, it is now our pleasure to call upon {speaker}, {desig}, to grace the stage and deliver the welcome address. Please join us in welcoming them with a warm round of applause.\n\n[Welcome Address is delivered]\n\n({assigned_mc}): Thank you very much for your encouraging words and warm welcoming remarks, which have beautifully set the tone for today's programme."
            stage_dirs = "[Lead applause as speaker approaches podium; step aside respectfully]"

        elif segment_type == "speaker_introduction":
            sp_name = data.get("speaker_name") or "Distinguished Guest Speaker"
            desig = data.get("designation") or "Eminent Subject Expert"
            topic = data.get("presentation_topic") or "Current Research Frontiers"
            bio = data.get("bio") or data.get("education") or f"An esteemed researcher and professional serving as {desig}."
            dialogue = f"({assigned_mc}): Now, let us commence with our core technical session. Please join us in welcoming our guest speaker, {sp_name}.\n\n{bio}\n\nToday, they will be taking us through an insightful session on '{topic}'. Please join us in welcoming {sp_name} to the podium.\n\n[Pause for applause as speaker takes the stage]"
            stage_dirs = f"[Call student volunteer to present sapling to {sp_name}; pause for applause]"

        elif segment_type == "prize_distribution":
            dialogue = f"({assigned_mc}): One of the most awaited moments of today's ceremony has arrived — the Prize Distribution Ceremony! This is the time when we recognize and reward the talent, innovation, and perseverance of our participants."
            comps = data.get("competitions") or []
            if comps:
                for c in comps:
                    dialogue += f"\n\nFor the event '{c.get('competition_name', 'Competition')}':"
                    for w in c.get("winners", []):
                        dialogue += f"\n- {w.get('position', 'Winner')}: {w.get('winner_names', 'Participant')} ({w.get('team_name', '')})"
            dialogue += f"\n\nCongratulations to all our stellar winners! Let us give them another thunderous round of applause!"
            stage_dirs = "[Invite dignitaries on stage to present trophies and certificates; upbeat background audio]"

        elif segment_type == "badge_distribution":
            presenter = data.get("presenter_name") or "our respected Faculty Coordinator"
            dialogue = f"({assigned_mc}): To recognize the dedication of our student leaders who have worked tirelessly throughout the year, it is now time for the Badge Distribution Ceremony. I now invite {presenter} on stage to do the honours of presenting the badges."
            leaders = data.get("recipients") or []
            if leaders:
                for l in leaders:
                    dialogue += f"\n\n{l.get('name')}, {l.get('role_title', 'Leader')} — please come forward to receive your badge."
            dialogue += "\n\nCongratulations to all our team leaders! We request all the Heads and Vice-Heads to kindly remain on stage together for a group photograph."
            stage_dirs = "[Call each leader forward individually; arrange on dais for official photograph]"

        elif segment_type == "memento_presentation":
            recip = data.get("recipient_name") or "our distinguished guest"
            pres = data.get("presenter_name") or "our faculty coordinator"
            gift = data.get("gift_type") or "memento"
            dialogue = f"({assigned_mc}): That was a truly perceptive and outstanding presentation. Let's put our hands together for their immense knowledge and insights. As a token of our reverence and heartfelt appreciation, we request {pres} to present {recip} with a {gift} on stage."
            stage_dirs = "[Lead applause; memento presented; photo opportunity on dais]"

        elif segment_type == "vote_of_thanks":
            presenter = data.get("speaker_name") or "our faculty coordinator"
            dialogue = f"({assigned_mc}): To formally conclude today's programme, we would like to call upon {presenter} to deliver the formal vote of thanks. Please join us in welcoming them to the podium."
            stage_dirs = "[Invite speaker to podium; pause for applause]"

        elif segment_type == "anthem_closing":
            anthem = data.get("anthem_name") or "CHRIST University Anthem"
            dialogue = f"({assigned_mc}): To bring this memorable occasion to a close, we request everyone to please rise in reverence for the {anthem}."
            stage_dirs = "[Assembly rises; all stand at strict attention as anthem plays]"

        elif segment_type == "feedback_announcements":
            dialogue = f"({assigned_mc}): We now request all participants to kindly scan the QR code displayed on the screen to provide your valuable feedback, after which participation certificates will be dispatched. Refreshments are provided outside in the lobby. Classes will resume as per schedule."
            stage_dirs = "[Point to screen displaying QR slide; announce dispersal in orderly fashion]"

        else:
            dialogue = f"({assigned_mc}): Welcome to the next segment of {title}. We now move forward to our next scheduled activity."
            stage_dirs = "[MC maintains poised stage presence]"

        return {
            "dialogue": dialogue,
            "stage_directions": stage_dirs,
            "transition_note": "Generated using verified university MC protocol.",
            "provider": "local_rules_engine",
            "model": "rule_based_fallback",
        }

    @classmethod
    def generate_full_script(
        cls,
        event_info: dict,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Dict:
        """Generate a complete structured MC script with full segment breakdown."""
        title = event_info.get("event_name") or event_info.get("title") or "Department Event"
        anchors = event_info.get("anchors") or [{"name": "Anchor 1"}, {"name": "Anchor 2"}]
        anchor_names = [a.get("name", f"Anchor {i+1}") for i, a in enumerate(anchors)]

        # Generate each standard segment
        segments = []
        standard_flow = [
            ("pre_event_announcement", "Pre-Event Announcements & Decorum", anchor_names[0]),
            ("opening_greeting", "Opening Greeting & Welcome", anchor_names[1] if len(anchor_names) > 1 else anchor_names[0]),
            ("dignitary_introduction", "Dignitary Acknowledgement", anchor_names[0]),
            ("welcome_address", "Welcome Address by HOD", anchor_names[1] if len(anchor_names) > 1 else anchor_names[0]),
            ("speaker_introduction", "Technical Speaker Introduction", anchor_names[0]),
            ("memento_presentation", "Speaker Appreciation & Memento", anchor_names[1] if len(anchor_names) > 1 else anchor_names[0]),
            ("vote_of_thanks", "Vote of Thanks", anchor_names[0]),
            ("anthem_closing", "University Anthem", anchor_names[1] if len(anchor_names) > 1 else anchor_names[0]),
            ("feedback_announcements", "Feedback QR & Dispersal", anchor_names[0]),
        ]

        full_script_lines = [f"=== {title} — Master MC Hosting Script ===\n"]

        for idx, (stype, stitle, mc_name) in enumerate(standard_flow, start=1):
            res = cls._generate_fallback_segment(
                stype,
                event_info,
                {"title": stitle, "assigned_mc": mc_name, "input_data": {}},
            )
            seg = {
                "id": str(idx),
                "title": stitle,
                "segment_type": stype,
                "sequence_order": idx,
                "assigned_mc": mc_name,
                "anchor": mc_name,
                "dialogue": res["dialogue"],
                "stage_directions": res["stage_directions"],
                "stage_direction": res["stage_directions"],
            }
            segments.append(seg)
            full_script_lines.append(f"--- Segment {idx}: {stitle} ---")
            full_script_lines.append(f"{res['stage_directions']}")
            full_script_lines.append(f"{res['dialogue']}\n")

        return {
            "title": f"{title} - MC Script",
            "segments": segments,
            "full_script": "\n".join(full_script_lines),
            "provider": "mc_assistant_protocol",
            "model": "university_protocol_v2",
        }

    @classmethod
    def rewrite_text(
        cls,
        text: str,
        tone: str,
        action: str = "adjust_tone",
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> str:
        """Transform MC script text with specific stylistic actions."""
        prompt = f"""
Transform the following MC hosting dialogue for a university department event:

ORIGINAL TEXT:
{text}

DESIRED TONE: {tone}
TRANSFORMATION GOAL: {action}
(Actions: 'formalize' = more elevated & formal; 'conversational' = more natural & engaging; 'shorten' = punchy & concise; 'expand' = elaborate with rich detail; 'fix_grammar' = polish phrasing; 'add_transition' = add smooth stage handover).

Return ONLY the revised spoken dialogue. Preserve speaker tags like (MC 1): or (Anchor 2):.
"""
        try:
            raw_text, _, _ = AIService.generate_with_resilient_fallback(
                prompt=prompt,
                system_instruction=SYSTEM_MC_INSTRUCTION,
                provider_name=provider_name,
                model_name=model_name,
            )
            return raw_text.strip()
        except Exception:
            return text

    @classmethod
    def generate_segment(
        cls,
        segment_type: str,
        event_info: dict,
        current_content: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Dict:
        """Convenience method matching API routes for generating an individual segment."""
        segment_info = {
            "title": segment_type.replace("_", " ").title(),
            "segment_type": segment_type,
            "current_content": current_content,
        }
        return cls.generate_segment_dialogue(
            segment_type=segment_type,
            event_info=event_info,
            segment_info=segment_info,
            action="enhance" if current_content else "generate",
            current_dialogue=current_content,
            user_prompt=custom_instructions,
            provider_name=provider_name,
            model_name=model_name,
        )

    @classmethod
    def rewrite_or_adjust_tone(
        cls,
        text: str,
        target_tone: str,
        action: str = "adjust_tone",
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Dict:
        """Convenience method matching API routes for rewriting or adjusting dialogue tone."""
        improved = cls.rewrite_text(
            text=text,
            tone=target_tone,
            action=action,
            provider_name=provider_name,
            model_name=model_name,
        )
        return {
            "improved_text": improved,
            "original_text": text,
            "tone": target_tone,
            "action": action,
        }

