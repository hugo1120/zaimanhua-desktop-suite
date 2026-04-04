import { create } from "zustand";

interface SearchPageState {
  inputKeyword: string;
  submittedKeyword: string;
  recentItems: any[];
  recentPage: number;
  recentHasMore: boolean;
  scrollY: number;
}

interface LibraryPageState {
  inputKeyword: string;
  submittedKeyword: string;
  selectedLetter: string;
  sortMode: any;
  statusFilter: any;
  scrollY: number;
}

interface ViewState {
  searchPage: SearchPageState;
  libraryPage: LibraryPageState;
  setSearchPageState: (state: Partial<SearchPageState>) => void;
  setLibraryPageState: (state: Partial<LibraryPageState>) => void;
}

const initialSearchState: SearchPageState = {
  inputKeyword: "",
  submittedKeyword: "",
  recentItems: [],
  recentPage: 1,
  recentHasMore: true,
  scrollY: 0,
};

const initialLibraryState: LibraryPageState = {
  inputKeyword: "",
  submittedKeyword: "",
  selectedLetter: "ALL",
  sortMode: "title",
  statusFilter: "all",
  scrollY: 0,
};

export const useViewStore = create<ViewState>((set) => ({
  searchPage: initialSearchState,
  libraryPage: initialLibraryState,
  setSearchPageState: (patch) =>
    set((state) => ({ searchPage: { ...state.searchPage, ...patch } })),
  setLibraryPageState: (patch) =>
    set((state) => ({ libraryPage: { ...state.libraryPage, ...patch } })),
}));
