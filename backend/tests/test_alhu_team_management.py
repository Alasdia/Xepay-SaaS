"""Gestion d'équipe réservée au propriétaire via Alhu (demande explicite
du 2026-11-27 : "des outils spécifiques dont seul le owner du workspace
peut demander à Alhu d'effectue une lecteur ou même de faire certaines
modifications concernant son equipe") - 2 angles, même défense en
profondeur que test_alhu_workspace_isolation.py :

1. OFFRE D'OUTIL : _build_tools(is_owner=False) ne doit JAMAIS contenir
   list_team_members/change_member_role/remove_team_member - un non-
   owner ne doit même pas pouvoir voir que ces outils existent.
2. EXÉCUTION : même si cette offre était contournée, _require_owner (et
   donc chacun des 3 outils, qui l'appelle en premier) doit bloquer
   indépendamment un appelant qui n'est pas réellement owner en base -
   jamais une confiance aveugle dans ce qui a été proposé plus haut.
   Et pour un vrai owner : les mêmes règles que routes/users.py
   (propriétaire protégé, rôle assignable valide, auto-retrait bloqué),
   plus un log_security_event marqué "(via Alhu)".

Même conventions que test_alhu_workspace_isolation.py (SQLite mémoire,
WorkspaceUser réels, pas de dépendance au LLM - non déterministe)."""
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models import UserDB, WorkspaceUser, SecurityEvent
from backend.services import alhu_service

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base.metadata.create_all(bind=engine)


class AlhuTeamToolOfferingTests(unittest.TestCase):
    """_build_tools ne doit jamais exposer les outils d'équipe à un
    non-owner - vérifié sur les NOMS d'outils envoyés au modèle, pas sur
    un comportement exécuté."""

    _OWNER_ONLY_NAMES = {"list_team_members", "change_member_role", "remove_team_member"}

    def setUp(self):
        # _build_tools interroge désormais aussi une VRAIE capacité de
        # workspace (request_shopify_store) - un workspace_id réel (même
        # inexistant en base, get_effective_min_role retombe sur
        # CAPABILITY_DEFAULTS sans erreur) est nécessaire, plus un simple
        # booléen is_owner.
        self.db = TestingSessionLocal()
        self.workspace_id = f"ws-tools-{id(self)}"

    def tearDown(self):
        self.db.close()

    def test_owner_only_tools_hidden_for_non_owner(self):
        tools = alhu_service._build_tools(self.db, self.workspace_id, "membre", is_owner=False)
        names = {t["name"] for t in tools}
        self.assertFalse(self._OWNER_ONLY_NAMES & names)

    def test_owner_only_tools_offered_for_owner(self):
        tools = alhu_service._build_tools(self.db, self.workspace_id, "owner", is_owner=True)
        names = {t["name"] for t in tools}
        self.assertTrue(self._OWNER_ONLY_NAMES.issubset(names))

    def test_base_tools_always_offered_regardless_of_role(self):
        base_names = {t["name"] for t in alhu_service._BASE_TOOLS}
        for role, is_owner in (("owner", True), ("membre", False)):
            names = {t["name"] for t in alhu_service._build_tools(self.db, self.workspace_id, role, is_owner)}
            self.assertTrue(base_names.issubset(names))

    def test_shopify_store_tool_offered_only_for_owner_by_default(self):
        # manage_shopify_integration = "owner" par défaut (aucune
        # surcharge posée pour ce workspace jetable) - un non-owner ne
        # doit pas voir request_shopify_store, un owner si.
        owner_tools = {t["name"] for t in alhu_service._build_tools(self.db, self.workspace_id, "owner", True)}
        member_tools = {t["name"] for t in alhu_service._build_tools(self.db, self.workspace_id, "membre", False)}
        self.assertIn("request_shopify_store", owner_tools)
        self.assertNotIn("request_shopify_store", member_tools)


class AlhuTeamToolExecutionTests(unittest.TestCase):
    """2 workspaces réels, avec un owner et un non-owner chacun -
    exécution directe des fonctions (jamais via le LLM, non
    déterministe)."""

    def setUp(self):
        self.db = TestingSessionLocal()
        suffix = id(self)

        self.owner = UserDB(email=f"alhu-team-owner-{suffix}@example.com", password="x")
        self.member = UserDB(email=f"alhu-team-member-{suffix}@example.com", password="x")
        self.outsider = UserDB(email=f"alhu-team-outsider-{suffix}@example.com", password="x")
        self.db.add_all([self.owner, self.member, self.outsider])
        self.db.flush()

        self.workspace_id = self.owner.id
        self.db.add(WorkspaceUser(user_id=self.owner.id, workspace_id=self.workspace_id, role="owner"))
        self.db.add(WorkspaceUser(user_id=self.member.id, workspace_id=self.workspace_id, role="membre"))
        # outsider : owner de SON PROPRE workspace, jamais membre de celui
        # testé ici - sert à vérifier qu'un owner d'ailleurs ne peut rien
        # faire sur ce workspace.
        self.db.add(WorkspaceUser(user_id=self.outsider.id, workspace_id=self.outsider.id, role="owner"))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_require_owner_blocks_non_owner_member(self):
        error = alhu_service._require_owner(self.db, self.workspace_id, self.member.id)
        self.assertIsNotNone(error)

    def test_require_owner_blocks_owner_of_another_workspace(self):
        error = alhu_service._require_owner(self.db, self.workspace_id, self.outsider.id)
        self.assertIsNotNone(error)

    def test_require_owner_allows_real_owner(self):
        error = alhu_service._require_owner(self.db, self.workspace_id, self.owner.id)
        self.assertIsNone(error)

    def test_list_team_members_blocked_for_non_owner(self):
        result = alhu_service._list_team_members(self.db, self.workspace_id, self.member.id)
        self.assertIn("error", result)

    def test_list_team_members_works_for_owner(self):
        result = alhu_service._list_team_members(self.db, self.workspace_id, self.owner.id)
        emails = {m["email"] for m in result["members"]}
        self.assertEqual(emails, {self.owner.email, self.member.email})

    def test_change_member_role_blocked_for_non_owner(self):
        result = alhu_service._change_member_role(self.db, self.workspace_id, self.member.id, self.member.email, "admin")
        self.assertIn("error", result)
        # Jamais exécuté silencieusement malgré l'erreur - le rôle réel
        # en base ne doit pas avoir changé.
        membership = self.db.query(WorkspaceUser).filter(
            WorkspaceUser.workspace_id == self.workspace_id, WorkspaceUser.user_id == self.member.id
        ).first()
        self.assertEqual(membership.role, "membre")

    def test_change_member_role_works_for_owner_and_logs_event(self):
        result = alhu_service._change_member_role(self.db, self.workspace_id, self.owner.id, self.member.email, "admin")
        self.assertEqual(result, {"success": True, "email": self.member.email, "new_role": "admin"})
        membership = self.db.query(WorkspaceUser).filter(
            WorkspaceUser.workspace_id == self.workspace_id, WorkspaceUser.user_id == self.member.id
        ).first()
        self.assertEqual(membership.role, "admin")
        event = self.db.query(SecurityEvent).filter(SecurityEvent.event_type == "member_role_changed").first()
        self.assertIsNotNone(event)
        self.assertIn("via Alhu", event.description)

    def test_change_member_role_rejects_invalid_role(self):
        result = alhu_service._change_member_role(self.db, self.workspace_id, self.owner.id, self.member.email, "owner")
        self.assertIn("error", result)

    def test_change_member_role_protects_owner(self):
        result = alhu_service._change_member_role(self.db, self.workspace_id, self.owner.id, self.owner.email, "admin")
        self.assertIn("error", result)

    def test_change_member_role_rejects_email_outside_workspace(self):
        result = alhu_service._change_member_role(self.db, self.workspace_id, self.owner.id, self.outsider.email, "admin")
        self.assertIn("error", result)

    def test_remove_team_member_blocked_for_non_owner(self):
        result = alhu_service._remove_team_member(self.db, self.workspace_id, self.member.id, self.member.email)
        self.assertIn("error", result)

    def test_remove_team_member_works_for_owner_and_logs_event(self):
        result = alhu_service._remove_team_member(self.db, self.workspace_id, self.owner.id, self.member.email)
        self.assertEqual(result, {"success": True, "email": self.member.email})
        remaining = self.db.query(WorkspaceUser).filter(
            WorkspaceUser.workspace_id == self.workspace_id, WorkspaceUser.user_id == self.member.id
        ).first()
        self.assertIsNone(remaining)
        event = self.db.query(SecurityEvent).filter(SecurityEvent.event_type == "member_removed").first()
        self.assertIsNotNone(event)
        self.assertIn("via Alhu", event.description)

    def test_remove_team_member_protects_owner(self):
        result = alhu_service._remove_team_member(self.db, self.workspace_id, self.owner.id, self.owner.email)
        self.assertIn("error", result)

    def test_remove_team_member_blocks_self_removal_by_owner(self):
        # L'owner est le seul à pouvoir appeler cet outil, mais ne doit
        # jamais pouvoir se retirer lui-même via Alhu (même garde que
        # delete_user côté routes/users.py).
        result = alhu_service._remove_team_member(self.db, self.workspace_id, self.owner.id, self.owner.email)
        self.assertIn("error", result)

    def test_get_workspace_info_available_to_any_member(self):
        info_owner = alhu_service._get_workspace_info(self.db, self.workspace_id, self.owner.id)
        info_member = alhu_service._get_workspace_info(self.db, self.workspace_id, self.member.id)
        self.assertEqual(info_owner["my_role"], "owner")
        self.assertEqual(info_member["my_role"], "membre")
        self.assertEqual(info_owner["member_count"], 2)
        self.assertEqual(info_member["member_count"], 2)

    def test_get_my_permissions_reflects_real_role(self):
        perms_owner = alhu_service._get_my_permissions(self.db, self.workspace_id, self.owner.id)
        perms_member = alhu_service._get_my_permissions(self.db, self.workspace_id, self.member.id)
        self.assertEqual(perms_owner["role"], "owner")
        self.assertEqual(perms_member["role"], "membre")
        # L'owner doit pouvoir tout ce que le "default_role" exige au
        # maximum (owner) - au moins une capacité vraie pour lui.
        self.assertTrue(any(c["allowed"] for c in perms_owner["capabilities"]))

    def test_get_my_permissions_blocked_for_non_member(self):
        result = alhu_service._get_my_permissions(self.db, self.workspace_id, self.outsider.id)
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
