import { createContext, useContext, useMemo, useState, type PropsWithChildren } from "react";

import { appConfig } from "./config";

const STORAGE_KEY = "sparc:fiscal-year";

type FiscalYearContextValue = {
  fiscalYear: number;
  setFiscalYear: (fiscalYear: number) => void;
  fiscalYearOptions: number[];
  fiscalYearRangeLabel: string;
  fiscalYearLabel: string;
};

const FiscalYearContext = createContext<FiscalYearContextValue | null>(null);

export function FiscalYearProvider({ children }: PropsWithChildren) {
  const [fiscalYear, setFiscalYearState] = useState(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    const storedYear = stored ? Number(stored) : NaN;
    return Number.isFinite(storedYear) ? storedYear : appConfig.fiscalYear;
  });

  const fiscalYearOptions = useMemo(() => fiscalYearOptionSet(appConfig.fiscalYear, fiscalYear), [fiscalYear]);

  function setFiscalYear(nextFiscalYear: number) {
    setFiscalYearState(nextFiscalYear);
    window.localStorage.setItem(STORAGE_KEY, String(nextFiscalYear));
  }

  return (
    <FiscalYearContext.Provider
      value={{
        fiscalYear,
        setFiscalYear,
        fiscalYearOptions,
        fiscalYearRangeLabel: fiscalYearRangeLabel(fiscalYear),
        fiscalYearLabel: `FY${fiscalYear}`,
      }}
    >
      {children}
    </FiscalYearContext.Provider>
  );
}

export function useFiscalYear() {
  const context = useContext(FiscalYearContext);
  if (!context) {
    throw new Error("useFiscalYear must be used within FiscalYearProvider");
  }
  return context;
}

export function fiscalYearRangeLabel(fiscalYear: number) {
  return `Jul ${fiscalYear - 1} - Jun ${fiscalYear}`;
}

function fiscalYearOptionSet(defaultFiscalYear: number, selectedFiscalYear: number) {
  const currentFiscalYear = fiscalYearForDate(new Date());
  const nearbyFiscalYears = [-2, -1, 0, 1, 2];
  const options = new Set<number>([selectedFiscalYear]);
  nearbyFiscalYears.forEach((offset) => {
    options.add(currentFiscalYear + offset);
    options.add(defaultFiscalYear + offset);
  });
  return Array.from(options)
    .filter((year) => Number.isFinite(year) && year >= 2020)
    .sort((left, right) => left - right);
}

function fiscalYearForDate(value: Date) {
  const calendarYear = value.getFullYear();
  const calendarMonth = value.getMonth() + 1;
  return calendarMonth >= 7 ? calendarYear + 1 : calendarYear;
}
