"""Captura de mudança real de janela. Dependências Windows são carregadas no sensor."""

from monitor.app_classifier import classificar_programa, carregar_classificacao
from monitor.multitask_analyzer import WindowSwitchAnalyzer
from monitor.usage_aggregator import UsageAggregator


def obter_janela_ativa(include_title=False):
    import psutil
    import pygetwindow as gw
    import win32process

    window = gw.getActiveWindow()
    if window is None:
        return None
    _, pid = win32process.GetWindowThreadProcessId(window._hWnd)
    result = {"handle": window._hWnd, "programa": psutil.Process(pid).name()}
    if include_title:
        result["titulo"] = window.title
    return result


def iniciar_monitoramento(stop_event, interval, emit, *, include_title=False,
                         multitask_enabled=True, observation_seconds=60,
                         alert_switches=4):
    rules = carregar_classificacao()
    analyzer = WindowSwitchAnalyzer(observation_seconds, alert_switches)
    usage = UsageAggregator()
    previous = None
    try:
        while not stop_event.is_set():
            current = obter_janela_ativa(include_title)
            key = (current["handle"], current["programa"]) if current else None
            if key != previous:
                previous = key
                if current:
                    program = current["programa"]
                    emit("window", "changed", {
                        "programa": program,
                        "categoria": classificar_programa(program, rules),
                        **({"titulo": current["titulo"]} if include_title else {}),
                    })
                    for item in usage.change(program):
                        emit("usage", "program_interval", item)
                    if multitask_enabled:
                        alert = analyzer.observe(key)
                        if alert:
                            emit("multitask", "frequent_switches", alert)
                else:
                    for item in usage.close():
                        emit("usage", "program_interval", item)
            stop_event.wait(interval)
    finally:
        for item in usage.close():
            emit("usage", "program_interval", item)
