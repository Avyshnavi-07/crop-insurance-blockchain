export enum PolicyStatus {
  ACTIVE = 0,
  AWAITING_ORACLES = 1,
  SETTLED = 2,
  UNDER_REVIEW = 3,
  DISPUTED = 4,
  CLOSED = 5,
}

export enum SeverityTier {
  NONE = 0,
  MODERATE = 1,
  SEVERE = 2,
  CATASTROPHIC = 3,
}

export enum CropCode {
  GROUNDNUT = 0,
  COTTON = 1,
}

export enum Region {
  ANANTAPUR = 0,
  KURNOOL = 1,
  KADAPA = 2,
}

export enum OracleSource {
  WEATHER = 0,
  SATELLITE = 1,
  SOIL = 2,
}

export interface OracleReport {
  submitted: boolean;
  tier: SeverityTier;
}

export interface PolicyReports {
  weather: OracleReport;
  satellite: OracleReport;
  soil: OracleReport;
}

export interface Policy {
  id: number;
  farmer: string;
  landHash: string;
  crop: CropCode;
  region: Region;
  sumInsured: bigint;
  premium: bigint;
  startTime: number;
  endTime: number;
  settlementTime: number;
  rulesHash: string;
  status: PolicyStatus;
  finalTier: SeverityTier;
  payoutAmount: bigint;
  payoutWithdrawn: boolean;
  reports?: PolicyReports;
}

export interface UserRoles {
  isAdmin: boolean;
  isWeatherOracle: boolean;
  isSatelliteOracle: boolean;
  isSoilOracle: boolean;
  isFraudChecker: boolean;
  isDisputeReviewer: boolean;
  isFarmer: boolean;
}
