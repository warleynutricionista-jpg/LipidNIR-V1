"""Rotas da base experimental: importação assistida, templates, consulta, cadastro manual."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from lipidence_modular.api.auth_routes import current_session
from lipidence_modular.application.context import AppContext
from lipidence_modular.application.contracts import AuthenticatedSession
from lipidence_modular.application.experimental_contracts import (
    BaseSummary,
    FilterOptions,
    ImportBatchOut,
    ImportPreview,
    ImportReport,
    ManualReferenceIn,
    ManualSampleIn,
    SampleFilters,
    SampleList,
    StagedImport,
    TemplateIn,
    TemplateOut,
)
from lipidence_modular.data.ingestion.plan import ImportKind, ImportPlan

MAX_UPLOAD_BYTES = 200 * 1024 * 1024
Session = Annotated[AuthenticatedSession, Depends(current_session)]


def build_experimental_router(context: AppContext) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["base experimental"])

    @router.post("/imports", response_model=StagedImport, status_code=201)
    async def stage_import(
        session: Session,
        file: Annotated[UploadFile, File()],
        kind: Annotated[ImportKind, Form()],
        study_id: Annotated[str, Form()],
    ) -> StagedImport:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            from lipidence_modular.data.importers.table import ImportFileError

            raise ImportFileError("arquivo acima do tamanho máximo aceito (200 MB)")
        return context.imports.stage(
            content=content, filename=file.filename or "", kind=kind, study_id=study_id,
            user=session.user,
        )

    @router.post("/imports/{import_batch_id}/preview", response_model=ImportPreview)
    def preview_import(import_batch_id: str, plan: ImportPlan, session: Session):
        return context.imports.preview(import_batch_id, plan, session.user)

    @router.post("/imports/{import_batch_id}/confirm", response_model=ImportReport)
    def confirm_import(import_batch_id: str, plan: ImportPlan, session: Session):
        return context.imports.confirm(import_batch_id, plan, session.user)

    @router.get("/imports/{import_batch_id}", response_model=ImportBatchOut)
    def get_import(import_batch_id: str, session: Session):
        return context.imports.get_batch(import_batch_id)

    @router.get("/templates", response_model=list[TemplateOut])
    def list_templates(session: Session):
        return context.imports.list_templates()

    @router.post("/templates", response_model=TemplateOut, status_code=201)
    def save_template(template: TemplateIn, session: Session):
        return context.imports.save_template(template, session.user)

    @router.get("/base/summary", response_model=BaseSummary)
    def summary(session: Session, study_id: str | None = None):
        return context.base.summary(study_id)

    @router.get("/base/filters", response_model=FilterOptions)
    def filter_options(session: Session):
        return context.base.filter_options()

    @router.get("/samples", response_model=SampleList)
    def list_samples(session: Session, filters: Annotated[SampleFilters, Query()]):
        return context.base.list_samples(filters)

    @router.post("/samples", status_code=201)
    def register_sample(data: ManualSampleIn, session: Session) -> dict[str, str]:
        return {"sample_id": context.imports.register_sample(data, session.user)}

    @router.post("/references", status_code=201)
    def register_reference(data: ManualReferenceIn, session: Session) -> dict[str, int]:
        return {"replicate": context.imports.register_reference(data, session.user)}

    return router
