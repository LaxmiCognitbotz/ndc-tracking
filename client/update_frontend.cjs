const fs = require('fs');

// 1. Create types file
const typesContent = `export interface NDCRecord {
  id: string;
  ndcAssignedDate: string;
  personNumber: string;
  employeeName: string;
  department: string;
  ndcStage: string;
  resignationDate: string;
  lastWorkingDate: string;
  ndcInitiatedDate: string;
  rmApprovalStatus: string;
  rmApprover: string;
  rmApprovalDate: string;
  itApprovalStatus: string;
  itApprover: string;
  itApprovalDate: string;
  abexApprovalStatus: string;
  abexApprover: string;
  abexApprovalDate: string;
  telecomApprovalStatus: string;
  telecomApprover: string;
  telecomApprovalDate: string;
  storeApprovalStatus: string;
  storeApprover: string;
  storeApprovalDate: string;
  safetyApprovalStatus: string;
  safetyApprover: string;
  safetyApprovalDate: string;
  administrationApprovalStatus: string;
  administrationApprover: string;
  administrationApprovalDate: string;
  securityApprovalStatus: string;
  securityApprover: string;
  securityApprovalDate: string;
  hrApprovalStatus: string;
  hrApprover: string;
  hrApprovalDate: string;
  gccHrApprovalStatus: string;
  gccHrApprover: string;
  gccHrApprovalDate: string;
  finalAbexApprovalStatus: string;
  finalAbexApprover: string;
  finalAbexApprovalDate: string;
  ndcCompletedDate: string;
  createdBy: string;
  fnfStatus: string;
  fnfDocument: string;
  fnfActionDate: string;
  fnfCompletedDate: string;
  recoveryPendingDept: string;
  recoveryAmount: number;
  recoveryStatus: string;
  openTextNotes: string;
}`;

if (!fs.existsSync('d:/ndc-reporting-project/client/src/types')) {
  fs.mkdirSync('d:/ndc-reporting-project/client/src/types');
}
fs.writeFileSync('d:/ndc-reporting-project/client/src/types/index.ts', typesContent);

// 2. Update Overview
let overview = fs.readFileSync('d:/ndc-reporting-project/client/src/features/overview/Overview.tsx', 'utf8');
overview = overview.replace(/import \{ mockNDCData \} from "\.\.\/\.\.\/data\/mockData";/, 'import { NDCRecord } from "../../types";\nimport axios from "axios";\nimport { useEffect } from "react";');
overview = overview.replace(/export function Overview\(\) \{/, `export function Overview() {\n  const [mockNDCData, setMockNDCData] = useState<NDCRecord[]>([]);\n  const [isLoading, setIsLoading] = useState(true);\n\n  useEffect(() => {\n    axios.get("/api/v1/ndc-records").then((res) => {\n      setMockNDCData(res.data);\n      setIsLoading(false);\n    });\n  }, []);\n\n  if (isLoading) return <div className="p-8 text-center">Loading...</div>;`);
fs.writeFileSync('d:/ndc-reporting-project/client/src/features/overview/Overview.tsx', overview);

// 3. Update Analytics
let analytics = fs.readFileSync('d:/ndc-reporting-project/client/src/features/analytics/Analytics.tsx', 'utf8');
// Fix hook imports if useEffect isn't there
analytics = analytics.replace(/import \{ useMemo, useState \} from "react";/, 'import { useMemo, useState, useEffect } from "react";\nimport axios from "axios";\nimport { NDCRecord } from "../../types";');
analytics = analytics.replace(/import \{ mockNDCData \} from "\.\.\/\.\.\/data\/mockData";/, '');
analytics = analytics.replace(/export function Analytics\(\) \{/, `export function Analytics() {\n  const [mockNDCData, setMockNDCData] = useState<NDCRecord[]>([]);\n  const [isLoading, setIsLoading] = useState(true);\n\n  useEffect(() => {\n    axios.get("/api/v1/ndc-records").then((res) => {\n      setMockNDCData(res.data);\n      setIsLoading(false);\n    });\n  }, []);\n\n  if (isLoading) return <div className="p-8 text-center">Loading...</div>;`);
// Find "typeof mockNDCData[0]" and replace with "NDCRecord"
analytics = analytics.replace(/typeof mockNDCData\[0\]/g, 'NDCRecord');
fs.writeFileSync('d:/ndc-reporting-project/client/src/features/analytics/Analytics.tsx', analytics);

// 4. Update FNFManagement
let fnf = fs.readFileSync('d:/ndc-reporting-project/client/src/features/fnf/FNFManagement.tsx', 'utf8');
fnf = fnf.replace(/import \{ useState, useMemo \} from "react";/, 'import { useState, useMemo, useEffect } from "react";\nimport axios from "axios";\nimport { NDCRecord } from "../../types";');
fnf = fnf.replace(/import \{ mockNDCData \} from "\.\.\/\.\.\/data\/mockData";/, '');
fnf = fnf.replace(/export function FNFManagement\(\) \{/, `export function FNFManagement() {\n  const [mockNDCData, setMockNDCData] = useState<NDCRecord[]>([]);\n  const [isLoading, setIsLoading] = useState(true);\n\n  useEffect(() => {\n    fetchData();\n  }, []);\n\n  const fetchData = () => {\n    axios.get("/api/v1/ndc-records").then((res) => {\n      setMockNDCData(res.data);\n      setIsLoading(false);\n    });\n  };\n\n  const handleSave = () => {\n    if (selectedRecord && (statusUpdate !== selectedRecord.fnfStatus || notesUpdate !== selectedRecord.openTextNotes)) {\n      axios.put(\`/api/v1/ndc-records/\${selectedRecord.id}\`, {\n        fnfStatus: statusUpdate,\n        openTextNotes: notesUpdate\n      }).then(() => fetchData());\n    }\n    setIsModalOpen(false);\n  };\n\n  if (isLoading) return <div className="p-8 text-center">Loading...</div>;`);

// Remove old handleSave logic
fnf = fnf.replace(/const handleSave = \(\) => \{\n    if \(selectedRecord\) \{\n      \/\/ In a real app, this would be an API call\n      console\.log\("Saving updates for", selectedRecord\.id, \{\n        fnfStatus: statusUpdate,\n        notes: notesUpdate,\n      \}\);\n    \}\n    setIsModalOpen\(false\);\n  \};/, '');
fs.writeFileSync('d:/ndc-reporting-project/client/src/features/fnf/FNFManagement.tsx', fnf);

// 5. Update EmailConfig
let email = fs.readFileSync('d:/ndc-reporting-project/client/src/features/email-config/EmailConfig.tsx', 'utf8');
email = email.replace(/import \{ useState \} from "react";/, 'import { useState, useEffect } from "react";\nimport axios from "axios";');
email = email.replace(/const initialRecipients: EmailRecipient\[\] = \[[\s\S]*?\];/, '');
email = email.replace(/export function EmailConfig\(\) \{/, `export function EmailConfig() {\n  const [recipients, setRecipients] = useState<EmailRecipient[]>([]);\n  const [isLoading, setIsLoading] = useState(true);\n\n  useEffect(() => {\n    fetchData();\n  }, []);\n\n  const fetchData = () => {\n    axios.get("/api/v1/email-recipients").then(res => {\n      setRecipients(res.data);\n      setIsLoading(false);\n    });\n  };\n\n  if (isLoading) return <div className="p-8 text-center">Loading...</div>;`);
email = email.replace(/const handleAddRecipient = \(\) => \{[\s\S]*?\}\s*\};/, `const handleAddRecipient = () => {\n    if (newRecipient.name && newRecipient.email && newRecipient.department) {\n      axios.post("/api/v1/email-recipients", newRecipient).then(() => {\n        fetchData();\n        setNewRecipient({ name: "", email: "", department: "", role: "" });\n        setIsAdding(false);\n      });\n    }\n  };`);
email = email.replace(/const handleRemoveRecipient = \(id: string\) => \{[\s\S]*?\}\s*\};/, `const handleRemoveRecipient = (id: string) => {\n    if (confirm("Are you sure you want to remove this recipient?")) {\n      axios.delete(\`/api/v1/email-recipients/\${id}\`).then(() => fetchData());\n    }\n  };`);
fs.writeFileSync('d:/ndc-reporting-project/client/src/features/email-config/EmailConfig.tsx', email);

console.log("Frontend successfully updated!");
