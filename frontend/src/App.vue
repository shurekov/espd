<script setup lang="ts">
import { computed, ref } from "vue";
import { requestDocumentCheck } from "@/api/checkDocument";
import PdfViewer from "@/components/PdfViewer.vue";

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
import type {
  CheckResult,
  DocumentPreview,
  NormativeData,
  ProfileId,
  Status,
} from "@/types";

const profileOptions: Record<
    ProfileId,
    {
      title: string;
      standard: string;
      description: string;
    }
> = {
  ved: {
    title: "Ведомость эксплуатационных документов",
    standard: "ГОСТ 19.507-79",
    description:
        "ИИ выполняет шесть проверок. Пять структурных правил дополнительно проходят независимый программный контроль.",
  },
  rsp: {
    title: "Руководство системного программиста",
    standard: "ГОСТ 19.503-79",
    description:
        "ИИ выполняет восемь проверок отдельными запросами. Аннотация и содержание дополнительно проходят независимый программный контроль.",
  },
  rop: {
    title: "Руководство оператора",
    standard: "ГОСТ 19.505-79",
    description:
        "ИИ выполняет шесть проверок отдельными запросами. Аннотация, содержание и ограниченные случаи сообщений дополнительно проходят независимый программный контроль.",
  },
  opr: {
    title: "Описание программы",
    standard: "ГОСТ 19.402-78",
    description:
        "ИИ выполняет девять проверок отдельными запросами. Аннотация, содержание и явные сведения о функциональных ограничениях дополнительно проходят ограниченный независимый программный контроль.",
  },
};

const selectedFile = ref<File | null>(null);
const selectedProfile = ref<ProfileId>("ved");
const result = ref<CheckResult | null>(null);
const preview = ref<DocumentPreview | null>(null);
const normative = ref<NormativeData | null>(null);
const selectedRuleId = ref<string | null>(null);

const selectedCheck = computed(() => {
  if (!result.value || !selectedRuleId.value) {
    return null;
  }

  return (
      result.value.checks.find(
          (check) => check.rule_id === selectedRuleId.value,
      ) ?? null
  );
});

const selectedNormativeRule = computed(() => {
  if (!normative.value || !selectedRuleId.value) {
    return null;
  }

  return normative.value.rules[selectedRuleId.value] ?? null;
});

function selectRule(ruleId: string) {
  selectedRuleId.value = ruleId;
}
const resultFilename = ref("");
const loading = ref(false);
const errorMessage = ref("");

const statusLabels: Record<Status, string> = {
  pass: "Пройдено",
  fail: "Несоответствие",
  review: "Нужна проверка",
};

const ruleDisplayIds: Record<string, string> = {
  "RSP-01": "RSP-1.1.1",
  "RSP-02": "RSP-1.1.2",
  "RSP-03": "RSP-2.1",
  "RSP-04": "RSP-2.2",
  "RSP-05": "RSP-2.3",
  "RSP-06": "RSP-2.4",
  "RSP-07": "RSP-2.5",
  "RSP-08": "RSP-2.6",
};

function displayRuleId(ruleId: string): string {
  return ruleDisplayIds[ruleId] ?? ruleId;
}

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
  preview.value = null;
  normative.value = null;
  selectedRuleId.value = null;
}

function onProfileChange() {
  errorMessage.value = "";
  result.value = null;
  preview.value = null;
  normative.value = null;
  selectedRuleId.value = null;
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

  const baseName = (resultFilename.value || "документ")
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

  try {
    const data = await requestDocumentCheck(
        selectedFile.value,
        selectedProfile.value,
    );

    result.value = data.result;
    resultFilename.value = data.filename;
    preview.value = data.preview;
    normative.value = data.normative;
    const firstIssue = data.result.checks.find(
        (check) => check.status !== "pass",
    );

    selectedRuleId.value = (
        firstIssue ?? data.result.checks[0] ?? null
    )?.rule_id ?? null;
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
    <div class="mx-auto max-w-7xl space-y-8">
        <p class="mb-2 font-mono text-xs uppercase tracking-widest text-stone-500">
          {{ profileOptions[selectedProfile].standard }}
        </p>
        <h1 class="text-4xl font-bold tracking-tight">
          ЕСПД Контроль
        </h1>

      <Card>
        <CardHeader>
          <CardTitle>{{ profileOptions[selectedProfile].title }}</CardTitle>
          <CardDescription>
            DOCX до 10 МБ. {{ profileOptions[selectedProfile].description }}
          </CardDescription>
        </CardHeader>

        <CardContent>
          <form class="space-y-4" @submit.prevent="checkDocument">

            <div class="space-y-2">
              <label for="document-profile" class="block text-sm font-medium">
                Тип документа
              </label>
              <select
                  id="document-profile"
                  v-model="selectedProfile"
                  :disabled="loading"
                  class="block min-h-11 w-full rounded-md border border-stone-300 bg-white p-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-stone-950 disabled:cursor-not-allowed disabled:opacity-60"
                  @change="onProfileChange"
              >
                <option value="ved">
                  Ведомость эксплуатационных документов
                </option>
                <option value="rsp">
                  Руководство системного программиста
                </option>
                <option value="rop">
                  Руководство оператора
                </option>
                <option value="opr">
                  Описание программы
                </option>
              </select>
            </div>
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

        <section v-if="preview" class="space-y-4">
          <div>
            <h2 class="text-2xl font-semibold">
              Документ и нормативное требование
            </h2>
            <p class="mt-1 text-sm text-stone-500">
              Выберите правило в списке ниже, чтобы увидеть причину
              и соответствующее требование ГОСТа.
            </p>
          </div>

          <div class="grid gap-4 xl:grid-cols-2">
            <div class="min-w-0">
              <h3 class="mb-2 font-semibold">
                Загруженный документ
              </h3>

              <div class="h-[700px]">
                <PdfViewer :src="preview.document_pdf_url" />
              </div>
            </div>

            <div class="min-w-0">
              <h3 class="mb-2 font-semibold">
                {{ normative?.document.standard ?? "Нормативный документ" }}
              </h3>

              <div class="h-[700px]">
                <PdfViewer
                    :src="normative?.document.pdf_url ?? null"
                    :page="selectedNormativeRule?.page ?? null"
                />
              </div>
            </div>
          </div>

          <div
              v-if="selectedCheck"
              class="space-y-3 border border-stone-300 bg-white p-4"
          >
            <div>
              <h3 class="font-semibold">
                Причина по правилу {{ displayRuleId(selectedCheck.rule_id) }}
              </h3>
              <p class="mt-2 leading-6">
                {{ selectedCheck.comment }}
              </p>
            </div>

            <div v-if="selectedNormativeRule" class="border-t pt-3">
              <h4 class="font-semibold">
                Требование · {{ selectedNormativeRule.source }}
              </h4>
              <p class="mt-2 leading-6 text-stone-700">
                {{ selectedNormativeRule.requirement }}
              </p>
            </div>

            <p class="font-mono text-xs text-stone-500">
              Evidence ID:
              {{ selectedCheck.evidence.join(", ") || "не указаны" }}
            </p>
          </div>

          <p
              v-if="preview.unresolved_evidence_ids.length"
              class="text-sm text-amber-700"
          >
            Не удалось найти в DOCX:
            {{ preview.unresolved_evidence_ids.join(", ") }}
          </p>
        </section>

        <Accordion type="single" collapsible class="rounded-lg border bg-white px-4">
          <AccordionItem
              v-for="check in result.checks"
              :key="check.rule_id"
              :value="check.rule_id"
          >
            <AccordionTrigger @click="selectRule(check.rule_id)">
              <span class="flex flex-wrap items-center gap-3">
                <span class="font-mono font-semibold">
                  {{ displayRuleId(check.rule_id) }}
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