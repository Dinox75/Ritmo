"""Scope a WebView2 prompt input without touching background settings fields."""


def prompt_field(ok_button, allowed_pids=None):
    container=ok_button
    for _ in range(20):
        container=container.parent()
        if container is None:return None
        if allowed_pids is not None and getattr(getattr(container,'element_info',None),'process_id',None) not in allowed_pids:
            return None
        # WebView2 labels the Edit itself with the prompt; some providers expose
        # no separate Text node. Background inputs have different labels.
        edits=[item for item in container.descendants(control_type='Edit')
               if getattr(getattr(item,'element_info',None),'name','').startswith('Digite APAGAR')]
        if len(edits)==1:return edits[0]
    return None
