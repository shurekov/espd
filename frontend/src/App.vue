<script setup lang="ts">
import { ref } from "vue";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type Status = "pass" | "fail" | "review";

type Check = {
  rule_id: string;
  observation: string;
  evidence: string[];
  status: Status;
  comment: string;
  agreement: boolean | null;
  ai: {
    status: Status;
    comment: string;
  };
  control: {
    status: Status;
    comment: string;
    evidence: string[];
  } | null;
};

type CheckResult = {
  document_type: string;
  standard: string;
  checks: Check[];
  summary: string;
};

const selectedFile = ref<File | null>(null);
const result = ref<CheckResult | null>(null);
const resultFilename = ref("");
const loading = ref(false);
const errorMessage = ref("");

const statusLabels: Record<Status, string> = {
  pass: "Пройдено",
  fail: "Несоответствие",
  review: "Нужна проверка",
};

function badgeVariant(status: Status) {
  if (status === "fail") return "destructive";
  if (status === "review") return "secondary";
  return "default";
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  selectedFile.value = input.files?.[0] ?? null;
  errorMessage.value = "";
  result.value = null;
}

function exportResult() {
  if (!result.value) {
    return;
  }

  const exportData = {
    source_file: resultFilename.value,
    exported_at: new Date().toISOString(),
    ...result.value,
  };

  const blob = new Blob(
      [JSON.stringify(exportData, null, 2)],
      { type: "application/json;charset=utf-8" },
  );

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  const baseName = (resultFilename.value || "ведомость")
      .replace(/\.[^.]+$/, "")
      .replace(/[\\/:*?"<>|]+/g, "_");

  link.href = url;
  link.download = `${baseName}_результат_проверки.json`;

  document.body.appendChild(link);
  link.click();
  link.remove();

  setTimeout(() => URL.revokeObjectURL(url), 0);
}

async function checkDocument() {
  if (!selectedFile.value) {
    errorMessage.value = "Выберите DOCX-документ.";
    return;
  }

  loading.value = true;
  errorMessage.value = "";
  result.value = null;

  const formData = new FormData();
  formData.append("file", selectedFile.value);

  try {
    const response = await fetch("/api/check", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Не удалось проверить документ.");
    }

    result.value = data.result;
    resultFilename.value = data.filename;
  } catch (error) {
    errorMessage.value =
        error instanceof Error
            ? error.message
            : "Неизвестная ошибка проверки.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="min-h-screen bg-stone-50 px-4 py-10 text-stone-950">
    <div class="mx-auto max-w-4xl space-y-8">
      <header class="border-b-2 border-stone-950 pb-6">
        <p class="mb-2 font-mono text-xs uppercase tracking-widest text-stone-500">
          Локальная проверка · ГОСТ 19.507-79
        </p>
        <h1 class="text-4xl font-bold tracking-tight">
          ЕСПД Контроль
        </h1>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Ведомость эксплуатационных документов</CardTitle>
          <CardDescription>
            DOCX до 10 МБ. ИИ выполняет шесть проверок, а структурные
            правила дополнительно проходят независимый контроль.
          </CardDescription>
        </CardHeader>

        <CardContent>
          <form class="space-y-4" @submit.prevent="checkDocument">
            <input
                type="file"
                accept=".docx"
                class="block w-full rounded-md border border-stone-300 bg-white p-3 text-sm"
                :disabled="loading"
                @change="onFileChange"
            >

            <Button type="submit" :disabled="loading">
              {{ loading ? "Выполняется проверка…" : "Проверить документ" }}
            </Button>
          </form>

          <p v-if="loading" class="mt-4 text-sm text-stone-500">
            Ожидаем ответ локальной модели. Это может занять несколько минут.
          </p>
        </CardContent>
      </Card>

      <Alert v-if="errorMessage" variant="destructive">
        <AlertTitle>Проверка не выполнена</AlertTitle>
        <AlertDescription>{{ errorMessage }}</AlertDescription>
      </Alert>

      <section v-if="result" class="space-y-5">

        <div class="flex justify-end">
          <Button
              type="button"
              variant="outline"
              @click="exportResult"
          >
            Скачать все выводы (JSON)
          </Button>
        </div>

        <div>
          <h2 class="text-2xl font-semibold">Результат проверки</h2>
          <p class="mt-1 text-sm text-stone-500">
            Файл: {{ resultFilename }}
          </p>
        </div>

        <Card>
          <CardContent class="pt-6">
            {{ result.summary }}
          </CardContent>
        </Card>

        <Accordion type="single" collapsible class="rounded-lg border bg-white px-4">
          <AccordionItem
              v-for="check in result.checks"
              :key="check.rule_id"
              :value="check.rule_id"
          >
            <AccordionTrigger>
              <span class="flex flex-wrap items-center gap-3">
                <span class="font-mono font-semibold">
                  {{ check.rule_id }}
                </span>
                <Badge :variant="badgeVariant(check.status)">
                  {{ statusLabels[check.status] }}
                </Badge>
              </span>
            </AccordionTrigger>

            <AccordionContent class="space-y-4 text-sm">
              <p class="leading-6">{{ check.comment }}</p>

              <div>
                <h3 class="font-semibold">Наблюдение ИИ</h3>
                <p class="mt-1 leading-6 text-stone-600">
                  {{ check.observation }}
                </p>
              </div>

              <div>
                <h3 class="font-semibold">Доказательства</h3>
                <p class="mt-1 font-mono text-xs text-stone-600">
                  {{ check.evidence.join(", ") || "Не указаны" }}
                </p>
              </div>

              <div class="border-t pt-4">
                <p>
                  <strong>ИИ:</strong>
                  {{ statusLabels[check.ai.status] }} —
                  {{ check.ai.comment }}
                </p>

                <p v-if="check.control" class="mt-2">
                  <strong>Независимый контроль:</strong>
                  {{ statusLabels[check.control.status] }} —
                  {{ check.control.comment }}
                </p>

                <p v-else class="mt-2 text-stone-500">
                  Правило оценено ИИ без структурного контроля.
                </p>

                <p
                    v-if="check.agreement === false"
                    class="mt-3 font-medium text-amber-700"
                >
                  Контуры разошлись. Требуется ручная проверка.
                </p>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </section>
    </div>
  </main>
</template>