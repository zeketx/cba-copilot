import { ApiError } from "@/lib/http";

export type ChatRequestError = {
  copy: string;
  retry: boolean;
  signOut: boolean;
  refreshThreads: boolean;
};

export function chatRequestError(caught: unknown): ChatRequestError {
  if (caught instanceof ApiError && caught.kind === "network") {
    return {
      copy: "Cannot reach the server.",
      retry: true,
      signOut: false,
      refreshThreads: false,
    };
  }
  if (caught instanceof ApiError) {
    if (caught.status === 401) {
      return {
        copy: "Your session ended. Sign in again.",
        retry: false,
        signOut: true,
        refreshThreads: false,
      };
    }
    if (caught.status === 403) {
      return {
        copy: "You do not have access to this chat or workspace.",
        retry: false,
        signOut: false,
        refreshThreads: false,
      };
    }
    if (caught.status === 404) {
      return {
        copy: "That chat no longer exists.",
        retry: false,
        signOut: false,
        refreshThreads: true,
      };
    }
    if (caught.status === 422) {
      return {
        copy: "That question could not be sent. Shorten or rephrase it.",
        retry: false,
        signOut: false,
        refreshThreads: false,
      };
    }
    if (caught.status === 502) {
      return {
        copy: "The answer service failed. Nothing was saved. Try again.",
        retry: true,
        signOut: false,
        refreshThreads: false,
      };
    }
  }
  if (caught instanceof Error) {
    return {
      copy: caught.message,
      retry: false,
      signOut: false,
      refreshThreads: false,
    };
  }
  return {
    copy: "The request failed.",
    retry: false,
    signOut: false,
    refreshThreads: false,
  };
}

export function isAbortError(caught: unknown): boolean {
  return caught instanceof DOMException && caught.name === "AbortError";
}
