import contextlib
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from test_cloudflare_release import load_worker_entry_module


class MarketplaceEmailPauseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.worker = load_worker_entry_module()

    def receipt(self, event_type):
        return SimpleNamespace(
            body={
                "type": event_type, "to": "private@example.invalid", "job_id": 42,
                "job_title": "Private project title", "nullable": None,
            },
            attempts=1, ack=Mock(), retry=Mock(),
        )

    async def test_optional_producers_stop_before_looking_up_recipients(self):
        worker = self.worker
        db = AsyncMock()
        queue = AsyncMock()
        for settings in (
            {}, {"WORKDOE_MARKETPLACE_EMAIL_ENABLED": "false"},
            {"WORKDOE_MARKETPLACE_EMAIL_ENABLED": "treu"},
            {"WORKDOE_MARKETPLACE_EMAIL_ENABLED": "true", "WORKDOE_ENV": " StAgInG "},
        ):
            with self.subTest(settings=settings), patch.object(worker, "db_run", db):
                env = SimpleNamespace(EMAIL_QUEUE=SimpleNamespace(send=queue), **settings)
                self.assertFalse(worker.marketplace_email_enabled(env))
                await worker.queue_stale_match_reminders(env)
                self.assertFalse(await worker.queue_repeat_provider_invitation_email(
                    env, 1, 2, "Local fixture", "Washington", "DC",
                ))
                self.assertFalse(await worker.queue_contractor_lead_alert_fanout(env, 2))
                self.assertEqual(await worker.process_contractor_lead_alert_fanout(env, 2), 0)
        db.assert_not_awaited()
        queue.assert_not_awaited()
        self.assertTrue(worker.marketplace_email_enabled(SimpleNamespace(
            WORKDOE_ENV="production", WORKDOE_MARKETPLACE_EMAIL_ENABLED="true",
        )))

    async def test_native_shaped_dispatch_audits_then_acks_all_optional_receipts(self):
        worker = self.worker
        sender = AsyncMock()
        env = SimpleNamespace(EMAIL=SimpleNamespace(send=sender))
        events = [
            "stale-match-reminder", "repeat-provider-invitation",
            "contractor-lead-alert-fanout", "contractor-new-lead",
        ]
        receipts = [self.receipt(event) for event in events]
        audited = []

        async def record(_env, event, *, target_type, payload, status):
            receipt = receipts[len(audited)]
            receipt.ack.assert_not_called()
            self.assertEqual(event, "email-message-suppressed")
            self.assertEqual(target_type, "workdoe-email")
            self.assertEqual(status, "processed")
            self.assertEqual(payload, {
                "type": receipt.body["type"], "reason": "marketplace-email-paused", "attempts": 1,
            })
            audited.append(payload["type"])

        batch = SimpleNamespace(queue="workdoe-email", messages=receipts)
        db = AsyncMock()
        with patch.object(worker, "record_event", record), patch.object(worker, "db_run", db):
            await worker.Default.queue(SimpleNamespace(env=env), batch, env, object())
        self.assertEqual(audited, events)
        for receipt in receipts:
            receipt.ack.assert_called_once_with()
            receipt.retry.assert_not_called()
        sender.assert_not_awaited()
        db.assert_not_awaited()

    async def test_audit_failure_retries_only_failed_receipt_without_logging_body(self):
        worker = self.worker
        first = self.receipt("contractor-new-lead")
        second = self.receipt("stale-match-reminder")
        batch = SimpleNamespace(queue="workdoe-email", messages=[first, second])
        audit = AsyncMock(side_effect=[RuntimeError("private@example.invalid"), None])
        output = io.StringIO()
        with patch.object(worker, "record_event", audit), contextlib.redirect_stdout(output):
            await worker.Default.queue(SimpleNamespace(env=SimpleNamespace()), batch)
        first.retry.assert_called_once_with()
        first.ack.assert_not_called()
        second.retry.assert_not_called()
        second.ack.assert_called_once_with()
        self.assertEqual(json.loads(output.getvalue()), {
            "event": "queue-message-processing-failed", "binding": "EMAIL_QUEUE", "attempts": 1,
        })

    async def test_unknown_queue_retries_without_reading_body(self):
        class UnknownReceipt:
            retry = Mock()
            ack = Mock()

            @property
            def body(self):
                raise AssertionError("Must not read unrecognized queue payloads")

        worker = self.worker
        receipt = UnknownReceipt()
        batch = SimpleNamespace(queue="not-a-workdoe-queue", messages=[receipt])
        await worker.Default.queue(SimpleNamespace(env=SimpleNamespace()), batch)
        receipt.ack.assert_not_called()
        receipt.retry.assert_called_once()

    async def test_plain_json_serialization_preserves_null_and_rejects_large_objects(self):
        worker = self.worker
        binding = SimpleNamespace(send=AsyncMock())
        parser = Mock(side_effect=json.loads)
        with patch.object(worker, "JS_JSON", SimpleNamespace(parse=parser)):
            await worker.send_queue_json(binding, {"type": "fixture", "nullable": None})
            binding.send.assert_awaited_once_with({"type": "fixture", "nullable": None})
            parser.assert_called_once_with('{"type":"fixture","nullable":null}')
            binding.send.reset_mock()
            with self.assertRaises(worker.JsonDataError):
                await worker.send_queue_json(
                    binding, {"text": "x" * (worker.MAX_QUEUE_JSON_BODY_BYTES + 1)},
                )
            binding.send.assert_not_awaited()
