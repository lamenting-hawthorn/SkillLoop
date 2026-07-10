from __future__ import annotations

import argparse

from skillloop.application.review import ReviewService
from skillloop.interfaces.cli._shared import _store


def cmd_review_list(args: argparse.Namespace) -> int:
    store = _store(args)
    proposals = ReviewService(store).list_proposals(status=args.status, include_all=args.all)
    if not proposals:
        print("No proposals found.")
        return 0
    for proposal in proposals:
        print(f"{proposal.id[:12]}\t{proposal.status}\t{proposal.kind}\t{proposal.title}")
        if args.verbose:
            print(f"  reason: {proposal.reason}")
            print(f"  content: {proposal.content[:240].replace(chr(10), ' ')}")
    return 0


def cmd_review_approve(args: argparse.Namespace) -> int:
    store = _store(args)
    service = ReviewService(store)
    proposal = service.resolve(args.proposal_id)
    service.set_status(proposal, "approved")
    print(f"Approved {proposal.id}")
    return 0


def cmd_review_reject(args: argparse.Namespace) -> int:
    store = _store(args)
    service = ReviewService(store)
    proposal = service.resolve(args.proposal_id)
    service.set_status(proposal, "rejected")
    print(f"Rejected {proposal.id}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    from skillloop.apply.filesystem import export_approved

    store = _store(args)
    written = export_approved(store, out_dir=args.out_dir)
    if not written:
        print("No approved proposals to export.")
        return 0
    for path in written:
        print(path)
    return 0


__all__ = ["cmd_apply", "cmd_review_approve", "cmd_review_list", "cmd_review_reject"]
