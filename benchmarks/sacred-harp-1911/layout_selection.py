"""Opt-in Sacred Harp layout selection, using image-derived structure only."""
import xml.etree.ElementTree as ET


def structural_penalty(report, xml):
    """Prefer 3/4-part readings with the same voices continued across systems.

    No expected counts, title, reference score or note-error rate enters this rule.
    Raw wins ties, so cleanup must fix a visible structural problem to be selected.
    """
    root = ET.fromstring(xml)
    parts = len(root.findall('part'))
    staves, systems = report['staves'], report['systems']
    if not parts or not systems:
        return 1000.0
    part_distance = min(abs(parts - n) for n in (3, 4))
    average_group = staves / systems
    group_distance = min(abs(average_group - n) for n in (3, 4))
    continuity = abs(staves - parts * systems) / max(parts, 1)
    return 10 * part_distance + 10 * group_distance + continuity


def choose_layout(candidates):
    """Candidates are ordered (name, report, xml) triples; stable ties preserve raw."""
    scores = [{'name': name, 'penalty': structural_penalty(report, xml)}
              for name, report, xml in candidates]
    # Two broken interpretations cannot be ranked safely by this coarse score.
    # Switch only when a later candidate actually satisfies the structure checks.
    valid = [i for i, score in enumerate(scores) if score['penalty'] == 0]
    winner = valid[0] if valid else 0
    return scores[winner]['name'], scores
