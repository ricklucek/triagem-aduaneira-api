from dataclasses import dataclass, field

from app.models.process import (
    ImportProcessStageEnum,
    ImportProcessServiceTypeEnum,
    ImportProcessTaskStatusEnum,
)


@dataclass(frozen=True)
class ChecklistItemRule:
    item_key: str
    label: str
    required: bool = True


@dataclass(frozen=True)
class ProcessTaskRule:
    task_key: str
    name: str
    stage: ImportProcessStageEnum
    default_service_type: ImportProcessServiceTypeEnum
    position: int
    checklist_items: list[ChecklistItemRule] = field(default_factory=list)


PROCESS_TASK_RULES = [
    # =========================================================
    # PRE SHIPMENT
    # =========================================================
    ProcessTaskRule(
        task_key="abertura_processo",
        name="Abertura de processo",
        stage=ImportProcessStageEnum.PRE_SHIPMENT,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=10,
        checklist_items=[
            ChecklistItemRule("dados_processo_conferidos", "Dados do processo conferidos"),
            ChecklistItemRule("cliente_vinculado", "Cliente vinculado ao processo"),
            ChecklistItemRule("referencias_conferidas", "Referências internas e do cliente conferidas"),
        ],
    ),
    ProcessTaskRule(
        task_key="conferencia_documental",
        name="Conferência documental",
        stage=ImportProcessStageEnum.PRE_SHIPMENT,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=20,
        checklist_items=[
            ChecklistItemRule("invoice_recebida", "Invoice recebida"),
            ChecklistItemRule("packing_list_recebido", "Packing list recebido"),
            ChecklistItemRule("documentos_basicos_conferidos", "Documentos básicos conferidos"),
        ],
    ),
    ProcessTaskRule(
        task_key="conferencia_bl",
        name="Conferência do BL/AWB",
        stage=ImportProcessStageEnum.PRE_SHIPMENT,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=30,
        checklist_items=[
            ChecklistItemRule("bl_awb_recebido", "BL/AWB recebido"),
            ChecklistItemRule("dados_bl_awb_conferidos", "Dados do BL/AWB conferidos"),
        ],
    ),
    ProcessTaskRule(
        task_key="averbar_seguro",
        name="Averbar seguro da carga",
        stage=ImportProcessStageEnum.PRE_SHIPMENT,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=40,
        checklist_items=[
            ChecklistItemRule("dados_seguro_conferidos", "Dados para averbação conferidos"),
            ChecklistItemRule("seguro_averbado", "Seguro averbado"),
        ],
    ),

    # =========================================================
    # SHIPMENT IN TRANSIT
    # =========================================================
    ProcessTaskRule(
        task_key="confirmacao_embarque",
        name="Confirmação de embarque",
        stage=ImportProcessStageEnum.SHIPMENT_IN_TRANSIT,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=50,
        checklist_items=[
            ChecklistItemRule("embarque_confirmado", "Embarque confirmado"),
            ChecklistItemRule("datas_embarque_atualizadas", "Datas de embarque atualizadas"),
        ],
    ),
    ProcessTaskRule(
        task_key="planilha_descricao",
        name="Planilha de descrição e finalidade da importação",
        stage=ImportProcessStageEnum.SHIPMENT_IN_TRANSIT,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=60,
        checklist_items=[
            ChecklistItemRule("planilha_enviada_cliente", "Planilha enviada ao cliente"),
            ChecklistItemRule("planilha_recebida_cliente", "Planilha recebida do cliente"),
            ChecklistItemRule("descricao_validada", "Descrição e finalidade validadas"),
        ],
    ),
    ProcessTaskRule(
        task_key="instrucao_digitacao",
        name="Instrução para time de digitação",
        stage=ImportProcessStageEnum.SHIPMENT_IN_TRANSIT,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=70,
        checklist_items=[
            ChecklistItemRule("documentos_enviados_digitacao", "Documentos enviados para digitação"),
            ChecklistItemRule("orientacoes_enviadas_digitacao", "Orientações enviadas para digitação"),
        ],
    ),
    ProcessTaskRule(
        task_key="follow_agente",
        name="Follow com agente de cargas / armador",
        stage=ImportProcessStageEnum.SHIPMENT_IN_TRANSIT,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=80,
        checklist_items=[
            ChecklistItemRule("follow_realizado", "Follow realizado"),
            ChecklistItemRule("previsao_chegada_atualizada", "Previsão de chegada atualizada"),
        ],
    ),
    ProcessTaskRule(
        task_key="recebimento_bl",
        name="Recebimento do BL/AWB original",
        stage=ImportProcessStageEnum.SHIPMENT_IN_TRANSIT,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=90,
        checklist_items=[
            ChecklistItemRule("bl_original_recebido", "BL/AWB original recebido"),
            ChecklistItemRule("bl_original_conferido", "BL/AWB original conferido"),
        ],
    ),
    ProcessTaskRule(
        task_key="instrucao_dtc_dta",
        name="Instrução para DTC / DTA",
        stage=ImportProcessStageEnum.SHIPMENT_IN_TRANSIT,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=100,
        checklist_items=[
            ChecklistItemRule("tipo_transito_definido", "Tipo de trânsito definido"),
            ChecklistItemRule("instrucao_dta_dtc_enviada", "Instrução DTA/DTC enviada"),
        ],
    ),
    ProcessTaskRule(
        task_key="envio_numerario",
        name="Envio de numerário",
        stage=ImportProcessStageEnum.SHIPMENT_IN_TRANSIT,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=110,
        checklist_items=[
            ChecklistItemRule("numerario_calculado", "Numerário calculado"),
            ChecklistItemRule("numerario_enviado_cliente", "Numerário enviado ao cliente"),
        ],
    ),

    # =========================================================
    # CUSTOMS CLEARANCE
    # =========================================================
    ProcessTaskRule(
        task_key="confirmacao_atracacao",
        name="Confirmação de atracação",
        stage=ImportProcessStageEnum.CUSTOMS_CLEARANCE,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=120,
        checklist_items=[
            ChecklistItemRule("atracacao_confirmada", "Atracação confirmada"),
            ChecklistItemRule("data_atracacao_atualizada", "Data de atracação atualizada"),
        ],
    ),
    ProcessTaskRule(
        task_key="presenca_carga",
        name="Confirmação de presença de carga",
        stage=ImportProcessStageEnum.CUSTOMS_CLEARANCE,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=130,
        checklist_items=[
            ChecklistItemRule("presenca_carga_confirmada", "Presença de carga confirmada"),
        ],
    ),
    ProcessTaskRule(
        task_key="verificar_avarias",
        name="Verificar avarias",
        stage=ImportProcessStageEnum.CUSTOMS_CLEARANCE,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=140,
        checklist_items=[
            ChecklistItemRule("avarias_verificadas", "Avarias verificadas"),
            ChecklistItemRule("ocorrencia_registrada", "Ocorrência registrada, se aplicável", required=False),
        ],
    ),
    ProcessTaskRule(
        task_key="vistoria_mapa",
        name="Confirmar vistoria MAPA / Embalagem",
        stage=ImportProcessStageEnum.CUSTOMS_CLEARANCE,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=150,
        checklist_items=[
            ChecklistItemRule("necessidade_mapa_verificada", "Necessidade de MAPA/Embalagem verificada"),
            ChecklistItemRule("vistoria_confirmada", "Vistoria confirmada, se aplicável", required=False),
        ],
    ),
    ProcessTaskRule(
        task_key="pagamento_taxas_fi",
        name="Pagamento das taxas de frete internacional",
        stage=ImportProcessStageEnum.CUSTOMS_CLEARANCE,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=160,
        checklist_items=[
            ChecklistItemRule("taxas_fi_identificadas", "Taxas de frete internacional identificadas"),
            ChecklistItemRule("pagamento_taxas_fi_confirmado", "Pagamento das taxas confirmado"),
        ],
    ),
    ProcessTaskRule(
        task_key="apresentar_bl_original",
        name="Apresentar BL original ao agente + termo de demurrage",
        stage=ImportProcessStageEnum.CUSTOMS_CLEARANCE,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=170,
        checklist_items=[
            ChecklistItemRule("bl_original_apresentado", "BL original apresentado"),
            ChecklistItemRule("termo_demurrage_apresentado", "Termo de demurrage apresentado"),
        ],
    ),
    ProcessTaskRule(
        task_key="data_limite_demurrage",
        name="Formalizar data limite — free time demurrage",
        stage=ImportProcessStageEnum.CUSTOMS_CLEARANCE,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=180,
        checklist_items=[
            ChecklistItemRule("free_time_identificado", "Free time identificado"),
            ChecklistItemRule("data_limite_formalizada", "Data limite formalizada"),
        ],
    ),
    ProcessTaskRule(
        task_key="registro_di_duimp",
        name="Registro DI / DUIMP",
        stage=ImportProcessStageEnum.CUSTOMS_CLEARANCE,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=190,
        checklist_items=[
            ChecklistItemRule("declaracao_preparada", "Declaração preparada"),
            ChecklistItemRule("di_duimp_registrada", "DI/DUIMP registrada"),
        ],
    ),
    ProcessTaskRule(
        task_key="canal_parametrizacao",
        name="Canal de parametrização",
        stage=ImportProcessStageEnum.CUSTOMS_CLEARANCE,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=200,
        checklist_items=[
            ChecklistItemRule("canal_identificado", "Canal identificado"),
            ChecklistItemRule("tratativa_canal_realizada", "Tratativa do canal realizada"),
        ],
    ),
    ProcessTaskRule(
        task_key="liberacao_icms",
        name="Liberação do ICMS",
        stage=ImportProcessStageEnum.CUSTOMS_CLEARANCE,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=210,
        checklist_items=[
            ChecklistItemRule("icms_apurado", "ICMS apurado"),
            ChecklistItemRule("icms_liberado", "ICMS liberado"),
        ],
    ),

    # =========================================================
    # RELEASED FOR DELIVERY
    # =========================================================
    ProcessTaskRule(
        task_key="emissao_nf",
        name="Emissão de Nota Fiscal de entrada",
        stage=ImportProcessStageEnum.RELEASED_FOR_DELIVERY,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=220,
        checklist_items=[
            ChecklistItemRule("dados_nf_enviados", "Dados para NF enviados"),
            ChecklistItemRule("nf_emitida", "NF emitida"),
        ],
    ),
    ProcessTaskRule(
        task_key="retorno_nf",
        name="Retorno da NF",
        stage=ImportProcessStageEnum.RELEASED_FOR_DELIVERY,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=230,
        checklist_items=[
            ChecklistItemRule("nf_recebida", "NF recebida"),
            ChecklistItemRule("nf_conferida", "NF conferida"),
        ],
    ),
    ProcessTaskRule(
        task_key="apresentar_nf_terminal",
        name="Apresentar NF e BL colorido ao terminal",
        stage=ImportProcessStageEnum.RELEASED_FOR_DELIVERY,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=240,
        checklist_items=[
            ChecklistItemRule("nf_apresentada_terminal", "NF apresentada ao terminal"),
            ChecklistItemRule("bl_colorido_apresentado_terminal", "BL colorido apresentado ao terminal"),
        ],
    ),
    ProcessTaskRule(
        task_key="liberacao_terminal",
        name="Liberação do terminal",
        stage=ImportProcessStageEnum.RELEASED_FOR_DELIVERY,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=250,
        checklist_items=[
            ChecklistItemRule("terminal_liberado", "Terminal liberado"),
        ],
    ),
    ProcessTaskRule(
        task_key="contactar_transportadora",
        name="Contactar transportadora",
        stage=ImportProcessStageEnum.RELEASED_FOR_DELIVERY,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=260,
        checklist_items=[
            ChecklistItemRule("transportadora_contatada", "Transportadora contatada"),
            ChecklistItemRule("dados_coleta_enviados", "Dados de coleta enviados"),
        ],
    ),
    ProcessTaskRule(
        task_key="agendamento_carregamento",
        name="Agendamento do carregamento da carga",
        stage=ImportProcessStageEnum.RELEASED_FOR_DELIVERY,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=270,
        checklist_items=[
            ChecklistItemRule("carregamento_agendado", "Carregamento agendado"),
            ChecklistItemRule("janela_carregamento_confirmada", "Janela de carregamento confirmada"),
        ],
    ),
    ProcessTaskRule(
        task_key="formalizar_entrega",
        name="Formalizar data e horário de entrega",
        stage=ImportProcessStageEnum.RELEASED_FOR_DELIVERY,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=280,
        checklist_items=[
            ChecklistItemRule("data_entrega_formalizada", "Data de entrega formalizada"),
            ChecklistItemRule("horario_entrega_formalizado", "Horário de entrega formalizado"),
        ],
    ),
    ProcessTaskRule(
        task_key="devolucao_container",
        name="Confirmar devolução do container vazio",
        stage=ImportProcessStageEnum.RELEASED_FOR_DELIVERY,
        default_service_type=ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE,
        position=290,
        checklist_items=[
            ChecklistItemRule("container_devolvido", "Container vazio devolvido"),
            ChecklistItemRule("comprovante_devolucao_recebido", "Comprovante de devolução recebido"),
        ],
    ),
]

FI_TASK_KEYS = {
    "abertura_processo",
    "confirmacao_embarque",
    "follow_agente",
    "recebimento_bl",
    "confirmacao_atracacao",
    "presenca_carga",
    "pagamento_taxas_fi",
}

INSURANCE_TASK_KEYS = {
    "averbar_seguro",
    "verificar_avarias",
}

ROAD_FREIGHT_TASK_KEYS = {
    "contactar_transportadora",
    "agendamento_carregamento",
    "formalizar_entrega",
    "devolucao_container",
}


def resolve_task_service_type(task_key: str, active_services: set[str]) -> ImportProcessServiceTypeEnum:
    if task_key in FI_TASK_KEYS:
        if ImportProcessServiceTypeEnum.INTERNATIONAL_FREIGHT.value in active_services:
            return ImportProcessServiceTypeEnum.INTERNATIONAL_FREIGHT
        return ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE

    if task_key in INSURANCE_TASK_KEYS:
        if ImportProcessServiceTypeEnum.INTERNATIONAL_INSURANCE.value in active_services:
            return ImportProcessServiceTypeEnum.INTERNATIONAL_INSURANCE
        return ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE

    if task_key in ROAD_FREIGHT_TASK_KEYS:
        if ImportProcessServiceTypeEnum.ROAD_FREIGHT.value in active_services:
            return ImportProcessServiceTypeEnum.ROAD_FREIGHT
        return ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE

    return ImportProcessServiceTypeEnum.CUSTOMS_CLEARANCE

def resolve_initial_task_status(
    task_key: str,
    payload: dict,
) -> ImportProcessTaskStatusEnum:
    if task_key != "instrucao_dtc_dta":
        return ImportProcessTaskStatusEnum.PENDING

    tags = payload.get("tags") or []

    tag_types = {
        tag.get("tag_type")
        for tag in tags
        if isinstance(tag, dict)
    }

    has_dta_or_dtc = "dta" in tag_types or "dtc" in tag_types

    if not has_dta_or_dtc:
        return ImportProcessTaskStatusEnum.DONE

    return ImportProcessTaskStatusEnum.PENDING