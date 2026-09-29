"""
Skills: packaged, reusable instructions the agent can load on demand.

Each folder in skills/ holds a SKILL.md with a short YAML front-matter header
(name + description) followed by detailed instructions - the same layout as
Anthropic's Agent Skills.

Skills use *progressive disclosure*: only the one-line descriptions go into the
system prompt (cheap), and the model calls the `load_skill` tool to pull in the
full instructions when a skill is relevant. This keeps the context small while
still letting the agent follow detailed, domain-specific procedures.
"""
import os
import re

from rag import tokenize

BASE_DIR = os.path.dirname(__file__)


def _parse_skill(path: str) -> dict:
    with open(path) as f:
        text = f.read()
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"{path} is missing its --- front-matter block")
    meta = dict(line.split(":", 1) for line in match.group(1).splitlines() if ":" in line)
    return {
        "name": meta["name"].strip(),
        "description": meta["description"].strip(),
        "instructions": match.group(2).strip(),
        "path": os.path.relpath(path, BASE_DIR),
    }


class SkillLibrary:
    def __init__(self, directory: str = os.path.join(BASE_DIR, "skills")):
        self.skills: dict[str, dict] = {}
        for name in sorted(os.listdir(directory)):
            path = os.path.join(directory, name, "SKILL.md")
            if os.path.exists(path):
                skill = _parse_skill(path)
                self.skills[skill["name"]] = skill

    def catalog(self) -> str:
        """The lightweight listing that goes into the system prompt."""
        return "\n".join(f"- {s['name']}: {s['description']}" for s in self.skills.values())

    def load(self, name: str) -> dict:
        skill = self.skills.get(name)
        if not skill:
            return {"error": f"Unknown skill '{name}'. Available: {list(self.skills)}"}
        return {"name": skill["name"], "instructions": skill["instructions"]}

    def suggest(self, text: str, limit: int = 2) -> list[str]:
        """Keyword router used by the offline planner (an LLM chooses skills itself)."""
        words = set(tokenize(text))
        scored = []
        for skill in self.skills.values():
            overlap = len(words & set(tokenize(skill["description"])))
            if overlap:
                scored.append((overlap, skill["name"]))
        return [name for _, name in sorted(scored, reverse=True)[:limit]]
