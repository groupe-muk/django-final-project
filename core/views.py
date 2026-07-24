from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .models import Translation


@login_required
def history(request):

    query = request.GET.get("q", "").strip()

    translations = Translation.objects.filter(user=request.user).select_related(
        "source_lang", "target_lang"
    )

    if query:
        translations = translations.filter(
            Q(source_text__icontains=query) | Q(translated_text__icontains=query)
        )

    paginator = Paginator(translations, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "history.html",
        {"page_obj": page_obj, "query": query},
    )


@login_required
def delete_history(request, id):
    translation = get_object_or_404(Translation, id=id, user=request.user)
    translation.delete()
    return redirect("history")


@login_required
def clear_history(request):
    Translation.objects.filter(user=request.user).delete()
    return redirect("history")


@login_required
def reload_translation(request, id):
    translation = get_object_or_404(Translation, id=id, user=request.user)
    return render(request, "translation.html", {"translation": translation})
