<script setup lang="ts">
import {
  nextTick,
  onBeforeUnmount,
  ref,
  shallowRef,
  watch,
} from "vue";
import {
  getDocument,
  GlobalWorkerOptions,
} from "pdfjs-dist";
import type {
  PDFDocumentLoadingTask,
  PDFDocumentProxy,
  RenderTask,
} from "pdfjs-dist/types/src/display/api";
import PdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";

GlobalWorkerOptions.workerSrc = PdfWorker;

const props = withDefaults(
    defineProps<{
      src: string | null;
      page?: number | null;
    }>(),
    {
      page: null,
    },
);

const canvasElement = ref<HTMLCanvasElement | null>(null);
const pdfDocument = shallowRef<PDFDocumentProxy | null>(null);
const loading = ref(false);
const errorMessage = ref("");
const currentPage = ref(1);
const pageCount = ref(0);
const scale = ref(1.2);

let loadingTask: PDFDocumentLoadingTask | null = null;
let renderTask: RenderTask | null = null;
let loadGeneration = 0;
let renderGeneration = 0;

function isCancellation(error: unknown): boolean {
  return (
      error instanceof Error
      && error.name === "RenderingCancelledException"
  );
}

function clearDocument() {
  renderGeneration += 1;
  renderTask?.cancel();
  renderTask = null;

  if (loadingTask) {
    void loadingTask.destroy();
    loadingTask = null;
  } else if (pdfDocument.value) {
    void pdfDocument.value.destroy();
  }

  pdfDocument.value = null;
  pageCount.value = 0;
  currentPage.value = 1;
}

function normalizedPage(page: number | null | undefined): number {
  return Math.min(
      Math.max(page ?? 1, 1),
      Math.max(pageCount.value, 1),
  );
}

async function renderCurrentPage() {
  const document = pdfDocument.value;

  if (!document) {
    return;
  }

  const generation = ++renderGeneration;
  renderTask?.cancel();
  renderTask = null;
  errorMessage.value = "";

  try {
    const page = await document.getPage(currentPage.value);

    if (generation !== renderGeneration) {
      return;
    }

    await nextTick();

    const canvas = canvasElement.value;
    const context = canvas?.getContext("2d");

    if (!canvas || !context) {
      throw new Error("Не удалось подготовить область отображения PDF");
    }

    const viewport = page.getViewport({ scale: scale.value });
    const outputScale = window.devicePixelRatio || 1;

    canvas.width = Math.floor(viewport.width * outputScale);
    canvas.height = Math.floor(viewport.height * outputScale);
    canvas.style.width = `${Math.floor(viewport.width)}px`;
    canvas.style.height = `${Math.floor(viewport.height)}px`;

    renderTask = page.render({
      canvasContext: context,
      viewport,
      transform: (
          outputScale === 1
              ? undefined
              : [outputScale, 0, 0, outputScale, 0, 0]
      ),
    });

    await renderTask.promise;
  } catch (error) {
    if (
        generation !== renderGeneration
        || isCancellation(error)
    ) {
      return;
    }

    errorMessage.value = "Не удалось отобразить страницу PDF.";
  } finally {
    if (generation === renderGeneration) {
      renderTask = null;
    }
  }
}

async function loadDocument() {
  const generation = ++loadGeneration;

  clearDocument();
  errorMessage.value = "";

  if (!props.src) {
    loading.value = false;
    return;
  }

  loading.value = true;
  const task = getDocument(props.src);
  loadingTask = task;

  try {
    const document = await task.promise;

    if (generation !== loadGeneration) {
      void document.destroy();
      return;
    }

    pdfDocument.value = document;
    pageCount.value = document.numPages;
    currentPage.value = normalizedPage(props.page);

    await nextTick();
    await renderCurrentPage();
  } catch (error) {
    if (generation !== loadGeneration) {
      return;
    }

    errorMessage.value = "Не удалось загрузить PDF-документ.";
  } finally {
    if (generation === loadGeneration) {
      loading.value = false;
    }
  }
}

function goToPage(page: number) {
  if (!pdfDocument.value) {
    return;
  }

  currentPage.value = normalizedPage(page);
  void renderCurrentPage();
}

function changeScale(delta: number) {
  if (!pdfDocument.value) {
    return;
  }

  scale.value = Math.min(
      Math.max(scale.value + delta, 0.6),
      2.5,
  );
  void renderCurrentPage();
}

watch(
    () => props.src,
    () => void loadDocument(),
    { immediate: true },
);

watch(
    () => props.page,
    (page) => {
      if (page && pdfDocument.value) {
        goToPage(page);
      }
    },
);

onBeforeUnmount(() => {
  loadGeneration += 1;
  clearDocument();
});
</script>

<template>
  <section class="flex h-full min-h-0 flex-col border border-stone-300 bg-white">
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-stone-300 px-3 py-2 text-sm">
      <div class="flex items-center gap-2">
        <button
            type="button"
            class="rounded border border-stone-300 px-2 py-1 disabled:opacity-40"
            :disabled="!pdfDocument || currentPage <= 1"
            aria-label="Предыдущая страница"
            @click="goToPage(currentPage - 1)"
        >
          ←
        </button>

        <span class="min-w-20 text-center">
          {{ currentPage }} / {{ pageCount || "—" }}
        </span>

        <button
            type="button"
            class="rounded border border-stone-300 px-2 py-1 disabled:opacity-40"
            :disabled="!pdfDocument || currentPage >= pageCount"
            aria-label="Следующая страница"
            @click="goToPage(currentPage + 1)"
        >
          →
        </button>
      </div>

      <div class="flex items-center gap-2">
        <button
            type="button"
            class="rounded border border-stone-300 px-2 py-1 disabled:opacity-40"
            :disabled="!pdfDocument || scale <= 0.6"
            aria-label="Уменьшить масштаб"
            @click="changeScale(-0.2)"
        >
          −
        </button>

        <span class="min-w-12 text-center">
          {{ Math.round(scale * 100) }}%
        </span>

        <button
            type="button"
            class="rounded border border-stone-300 px-2 py-1 disabled:opacity-40"
            :disabled="!pdfDocument || scale >= 2.5"
            aria-label="Увеличить масштаб"
            @click="changeScale(0.2)"
        >
          +
        </button>
      </div>
    </div>

    <p
        v-if="errorMessage"
        class="border-b border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
    >
      {{ errorMessage }}
    </p>

    <div class="min-h-0 flex-1 overflow-auto bg-stone-200 p-4">
      <p
          v-if="!src"
          class="p-6 text-center text-sm text-stone-600"
      >
        PDF не выбран.
      </p>

      <p
          v-else-if="loading"
          class="p-6 text-center text-sm text-stone-600"
      >
        Загрузка PDF…
      </p>

      <canvas
          v-show="src && pdfDocument && !loading"
          ref="canvasElement"
          class="mx-auto block bg-white shadow-sm"
      ></canvas>
    </div>
  </section>
</template>