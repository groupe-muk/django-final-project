def home(request):
    from django.shortcuts import render

    return render(request, "core/translator.html")


def translator(request):
    from django.shortcuts import render

    return render(request, "core/translator.html")


def history(request):
    from django.shortcuts import render

    entries = [
        {
            "source": "English",
            "target": "French",
            "text": "The report was approved this morning.",
            "translation": "Le rapport a été approuvé ce matin.",
            "time": "2 min ago",
        },
        {
            "source": "Spanish",
            "target": "English",
            "text": "Necesitamos revisar los detalles finales.",
            "translation": "We need to review the final details.",
            "time": "14 min ago",
        },
        {
            "source": "German",
            "target": "English",
            "text": "Bitte senden Sie die aktualisierte Version.",
            "translation": "Please send the updated version.",
            "time": "1 hour ago",
        },
    ]

    return render(request, "core/history.html", {"entries": entries})
