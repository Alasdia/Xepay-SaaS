"""Optimisations coût/jeton d'Alhu (demande du 2026-11-27) - logique
pure, jamais d'appel réseau réel :

1. _trim_message_history : fenêtre glissante qui ne doit JAMAIS couper
   une paire tool_use/tool_result (l'API Anthropic l'interdit : un
   message "user" tool_result doit toujours être immédiatement précédé
   du message "assistant" qui a émis le tool_use correspondant), ni
   laisser l'historique démarrer par un message "assistant" (l'API
   exige "user" en premier).
2. _tools_with_cache_control : pose cache_control UNIQUEMENT sur le
   dernier outil, SANS jamais muter les listes globales partagées
   (_BASE_TOOLS etc.) - une mutation in-place corromprait un autre
   appel où cet outil ne serait plus en dernière position."""
import unittest

from backend.services import alhu_service


def _user(text):
    return {"role": "user", "content": text}


def _assistant_tool_use(tool_use_id, name="get_balance"):
    # Mime response.content (objets SDK avec .type/.id/.name en usage
    # réel) - ici de simples objets avec les attributs lus par
    # _stream_alhu_rounds, suffisant pour tester _trim_message_history
    # qui ne lit que message["role"], jamais le contenu détaillé d'un
    # message assistant.
    return {"role": "assistant", "content": [{"type": "tool_use", "id": tool_use_id, "name": name}]}


def _tool_result(tool_use_id):
    return {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": "{}"}]}


class TrimMessageHistoryTests(unittest.TestCase):
    def test_no_trim_when_under_the_limit(self):
        messages = [_user(f"m{i}") for i in range(5)]
        self.assertEqual(alhu_service._trim_message_history(messages, max_messages=8), messages)

    def test_trims_to_exact_window_when_cut_is_clean(self):
        # Que des tours simples "user" - aucune paire à préserver, la
        # coupe peut tomber n'importe où.
        messages = [_user(f"m{i}") for i in range(20)]
        trimmed = alhu_service._trim_message_history(messages, max_messages=8)
        self.assertEqual(trimmed, messages[-8:])

    def test_never_starts_on_an_orphan_tool_result(self):
        # Construit un historique où une coupe "naïve" aux 8 derniers
        # messages tomberait EXACTEMENT sur un tool_result, son
        # tool_use étant le message juste avant (donc exclu) - doit
        # être automatiquement inclus.
        messages = [_user("question initiale")]
        for i in range(10):
            messages.append(_assistant_tool_use(f"tu_{i}"))
            messages.append(_tool_result(f"tu_{i}"))
        messages.append(_user("question finale"))

        trimmed = alhu_service._trim_message_history(messages, max_messages=8)

        self.assertEqual(trimmed[0]["role"], "user")
        # Si le 1er message est un tool_result, son tool_use (message
        # juste avant dans l'historique complet) doit être le message
        # juste avant lui dans la fenêtre retenue aussi.
        if alhu_service._is_tool_result_message(trimmed[0]):
            self.fail("La fenêtre ne doit jamais démarrer sur un tool_result orphelin")

    def test_never_starts_with_an_assistant_message(self):
        messages = [_user("q0")]
        for i in range(10):
            messages.append(_assistant_tool_use(f"tu_{i}"))
            messages.append(_tool_result(f"tu_{i}"))
        trimmed = alhu_service._trim_message_history(messages, max_messages=4)
        self.assertNotEqual(trimmed[0]["role"], "assistant")

    def test_preserves_every_tool_use_tool_result_pair_fully(self):
        messages = [_user("q0")]
        for i in range(10):
            messages.append(_assistant_tool_use(f"tu_{i}"))
            messages.append(_tool_result(f"tu_{i}"))

        trimmed = alhu_service._trim_message_history(messages, max_messages=5)

        # Chaque tool_result présent dans la fenêtre doit avoir son
        # tool_use (même id) immédiatement avant lui.
        for idx, msg in enumerate(trimmed):
            if alhu_service._is_tool_result_message(msg):
                tool_use_id = msg["content"][0]["tool_use_id"]
                prev = trimmed[idx - 1]
                self.assertEqual(prev["role"], "assistant")
                self.assertEqual(prev["content"][0]["id"], tool_use_id)

    def test_converges_to_zero_when_everything_is_chained(self):
        # Toute la conversation n'est qu'une seule longue chaîne
        # tool_use/tool_result - la fenêtre doit remonter jusqu'au tout
        # premier message (garanti "user") plutôt que de planter.
        messages = [_user("q0")]
        for i in range(3):
            messages.append(_assistant_tool_use(f"tu_{i}"))
            messages.append(_tool_result(f"tu_{i}"))
        trimmed = alhu_service._trim_message_history(messages, max_messages=2)
        self.assertEqual(trimmed[0], messages[0])


class ToolsCacheControlTests(unittest.TestCase):
    def test_cache_control_only_on_last_tool(self):
        tools = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
        result = alhu_service._tools_with_cache_control(tools)
        self.assertNotIn("cache_control", result[0])
        self.assertNotIn("cache_control", result[1])
        self.assertEqual(result[2]["cache_control"], {"type": "ephemeral"})

    def test_never_mutates_shared_global_tool_lists(self):
        before = [dict(t) for t in alhu_service._BASE_TOOLS]
        alhu_service._tools_with_cache_control(list(alhu_service._BASE_TOOLS))
        after = alhu_service._BASE_TOOLS
        self.assertEqual(before, [dict(t) for t in after])
        self.assertNotIn("cache_control", after[-1])

    def test_build_tools_output_unaffected_by_previous_cache_control_call(self):
        # Appelle _tools_with_cache_control une 1re fois (owner, donc
        # _OWNER_ONLY_TOOLS en dernier) puis reconstruit pour un
        # non-owner (_BASE_TOOLS en dernier) - le 2e appel ne doit
        # jamais voir de cache_control résiduel posé par le 1er sur un
        # dict partagé.
        owner_tools = alhu_service._BASE_TOOLS + alhu_service._OWNER_ONLY_TOOLS
        alhu_service._tools_with_cache_control(owner_tools)
        self.assertNotIn("cache_control", alhu_service._OWNER_ONLY_TOOLS[-1])
        self.assertNotIn("cache_control", alhu_service._BASE_TOOLS[-1])


if __name__ == "__main__":
    unittest.main()
