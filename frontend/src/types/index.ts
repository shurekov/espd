export type Status = "pass" | "fail" | "review";

export type ProfileId = "ved" | "rsp" | "rop" | "opr";

export type Check = {
    rule_id: string;
    observation: string;
    evidence: string[];
    status: Status;
    comment: string;
    agreement: boolean | null;
    ai: {
        status: Status;
        comment: string;
        evidence: string[];
    };
    control: {
        status: Status;
        comment: string;
        evidence: string[];
    } | null;
};

export type CheckResult = {
    document_type: string;
    standard: string;
    checks: Check[];
    summary: string;
    diagnostics: Record<string, unknown>;
};

export type CheckResponse = {
    filename: string;
    profile_id: ProfileId;
    result: CheckResult;
    usage: Record<string, unknown>;
};