from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.ai_provider import ai_provider_status, enhance_analysis
from backend.database import save_analysis_result
from backend.ai_service import (
    analyze_contribution,
    analyze_completeness,
    analyze_methodology,
    analyze_novelty,
    analyze_quality,
    analyze_writing,
    generate_improvements,
    generate_journal_match,
    generate_readiness_report,
)
from backend.improvement import service as improvement_service
from backend.security import get_current_user, get_accessible_document

router = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])


class AnalysisPayload(BaseModel):
    document_id: str
    analysis: dict | None = None
    journal_id: str | None = None
    quality_analysis: dict | None = None
    selected_journal: str | None = None
    focus: str | None = None
    targets: list[dict] | None = None


def _document_analysis(payload: AnalysisPayload, user: dict) -> dict:
    document, _ = get_accessible_document(payload.document_id, user, capability="read")
    return payload.analysis or (json.loads(document["analysis_json"]) if document["analysis_json"] else {})


async def _store_module_result(module: str, payload: AnalysisPayload, baseline: dict, analysis: dict) -> dict:
    result = await enhance_analysis(module, analysis, baseline)
    save_analysis_result(payload.document_id, module, result)
    return result


@router.get("/ai/status")
async def get_ai_status():
    return ai_provider_status()


@router.post("/quality/analyze")
async def quality_analyze(payload: AnalysisPayload, user: dict = Depends(get_current_user)):
    if not payload.document_id:
        raise HTTPException(status_code=400, detail="Document ID is required.")
    analysis = _document_analysis(payload, user)
    try:
        result = analyze_quality(payload.document_id, analysis, payload.journal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await _store_module_result("quality", payload, result, analysis)


@router.post("/novelty/analyze")
async def novelty_analyze(payload: AnalysisPayload, user: dict = Depends(get_current_user)):
    if not payload.document_id:
        raise HTTPException(status_code=400, detail="Document ID is required.")
    analysis = _document_analysis(payload, user)
    result = analyze_novelty(payload.document_id, analysis)
    return await _store_module_result("novelty", payload, result, analysis)


@router.post("/methodology/analyze")
async def methodology_analyze(payload: AnalysisPayload, user: dict = Depends(get_current_user)):
    if not payload.document_id:
        raise HTTPException(status_code=400, detail="Document ID is required.")
    analysis = _document_analysis(payload, user)
    result = analyze_methodology(payload.document_id, analysis)
    return await _store_module_result("methodology", payload, result, analysis)


@router.post("/contribution/analyze")
async def contribution_analyze(payload: AnalysisPayload, user: dict = Depends(get_current_user)):
    if not payload.document_id:
        raise HTTPException(status_code=400, detail="Document ID is required.")
    analysis = _document_analysis(payload, user)
    result = analyze_contribution(payload.document_id, analysis)
    return await _store_module_result("contribution", payload, result, analysis)


@router.post("/completeness/analyze")
async def completeness_analyze(payload: AnalysisPayload, user: dict = Depends(get_current_user)):
    if not payload.document_id:
        raise HTTPException(status_code=400, detail="Document ID is required.")
    analysis = _document_analysis(payload, user)
    try:
        result = analyze_completeness(payload.document_id, analysis, payload.journal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await _store_module_result("completeness", payload, result, analysis)


@router.post("/writing/analyze")
async def writing_analyze(payload: AnalysisPayload, user: dict = Depends(get_current_user)):
    if not payload.document_id:
        raise HTTPException(status_code=400, detail="Document ID is required.")
    analysis = _document_analysis(payload, user)
    result = analyze_writing(payload.document_id, analysis)
    return await _store_module_result("writing", payload, result, analysis)


@router.post("/improvement/generate")
async def improvement_generate(payload: AnalysisPayload, user: dict = Depends(get_current_user)):
    if not payload.document_id:
        raise HTTPException(status_code=400, detail="Document ID is required.")
    analysis = _document_analysis(payload, user)
    try:
        result = generate_improvements(payload.document_id, analysis, payload.focus, payload.journal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await _store_module_result("improvement", payload, result, analysis)


@router.post("/improvement/assess")
async def improvement_assess(payload: AnalysisPayload, user: dict = Depends(get_current_user)):
    if not payload.document_id:
        raise HTTPException(status_code=400, detail="Document ID is required.")
    analysis = _document_analysis(payload, user)
    result = improvement_service.assess_manuscript(payload.document_id, analysis, payload.journal_id)
    save_analysis_result(payload.document_id, "improvement", result)
    return result


@router.post("/improvement/revise")
async def improvement_revise(payload: AnalysisPayload, user: dict = Depends(get_current_user)):
    if not payload.document_id:
        raise HTTPException(status_code=400, detail="Document ID is required.")
    analysis = _document_analysis(payload, user)
    return improvement_service.generate_revisions(payload.document_id, analysis, payload.targets)


@router.post("/improvement/experiments")
async def improvement_experiments(payload: AnalysisPayload, user: dict = Depends(get_current_user)):
    if not payload.document_id:
        raise HTTPException(status_code=400, detail="Document ID is required.")
    analysis = _document_analysis(payload, user)
    return improvement_service.recommend_experiments(payload.document_id, analysis)


@router.post("/journal/match")
async def journal_match(payload: AnalysisPayload, user: dict = Depends(get_current_user)):
    if not payload.document_id:
        raise HTTPException(status_code=400, detail="Document ID is required.")
    get_accessible_document(payload.document_id, user, capability="read")
    try:
        return generate_journal_match(payload.document_id, payload.analysis, payload.journal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/report/generate")
async def report_generate(payload: AnalysisPayload, user: dict = Depends(get_current_user)):
    if not payload.document_id:
        raise HTTPException(status_code=400, detail="Document ID is required.")
    analysis = _document_analysis(payload, user)
    try:
        result = generate_readiness_report(
            payload.document_id,
            analysis,
            payload.quality_analysis,
            payload.selected_journal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    save_analysis_result(payload.document_id, "readiness_report", result)
    return result
