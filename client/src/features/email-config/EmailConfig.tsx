import { useState, useEffect } from "react";
import axios from "../../lib/axios";
import { Mail, Plus, Trash2, Pencil, Check, X } from "lucide-react";
import { LoadingScreen } from "../../components/common/LoadingScreen";
import { toast } from "sonner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../../components/ui/alert-dialog";

interface EmailRecipient {
  id: string;
  name: string;
  email: string;
  department: string;
  role: string;
}

const DEPARTMENTS = [
  "RM",
  "IT",
  "Abex",
  "Telecom",
  "Store",
  "Safety",
  "Administration",
  "Security",
  "HR",
  "GCC HR",
  "Business Specific",
  "Final Abex",
  "Legatrix",
];

const EMPTY_FORM = { name: "", email: "", department: "", role: "" };

export function EmailConfig() {
  const [recipients, setRecipients] = useState<EmailRecipient[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Add form state
  const [isAdding, setIsAdding] = useState(false);
  const [newRecipient, setNewRecipient] = useState<Omit<EmailRecipient, "id">>(EMPTY_FORM);

  // Inline-edit state – stores the id being edited + a mutable copy of the row
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<Omit<EmailRecipient, "id">>(EMPTY_FORM);

  // Delete confirm
  const [recipientToDelete, setRecipientToDelete] = useState<string | null>(null);

  // Saving spinner for inline edit
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = () => {
    axios.get("/api/v1/email-recipients").then((res) => {
      const data = res.data?.data || res.data;
      setRecipients(Array.isArray(data) ? data : []);
      setIsLoading(false);
    });
  };

  // ── ADD ──────────────────────────────────────────────
  const handleAddRecipient = () => {
    if (!newRecipient.name || !newRecipient.email || !newRecipient.department) {
      toast.error("Name, Email, and Department are required.");
      return;
    }
    // Client-side duplicate check
    const emailLower = newRecipient.email.trim().toLowerCase();
    const isDuplicate = recipients.some((r) => r.email.toLowerCase() === emailLower);
    if (isDuplicate) {
      toast.error("A recipient with this email already exists.");
      return;
    }
    axios.post("/api/v1/email-recipients", { ...newRecipient, email: emailLower })
      .then(() => {
        fetchData();
        setNewRecipient(EMPTY_FORM);
        setIsAdding(false);
        toast.success("Recipient added successfully.");
      })
      .catch((err) => {
        const detail = err?.response?.data?.detail || "Failed to add recipient.";
        toast.error(detail);
      });
  };

  // ── EDIT ─────────────────────────────────────────────
  const startEdit = (recipient: EmailRecipient) => {
    setEditingId(recipient.id);
    setEditDraft({
      name: recipient.name,
      email: recipient.email,
      department: recipient.department,
      role: recipient.role,
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditDraft(EMPTY_FORM);
  };

  const saveEdit = () => {
    if (!editDraft.name || !editDraft.email || !editDraft.department) {
      toast.error("Name, Email, and Department are required.");
      return;
    }
    // Client-side duplicate check – exclude the row being edited
    const emailLower = editDraft.email.trim().toLowerCase();
    const isDuplicate = recipients.some(
      (r) => r.email.toLowerCase() === emailLower && r.id !== editingId
    );
    if (isDuplicate) {
      toast.error("Another recipient with this email already exists.");
      return;
    }
    setIsSaving(true);
    axios.put(`/api/v1/email-recipients/${editingId}`, { ...editDraft, email: emailLower })
      .then(() => {
        fetchData();
        setEditingId(null);
        setEditDraft(EMPTY_FORM);
        toast.success("Recipient updated successfully.");
      })
      .catch((err) => {
        const detail = err?.response?.data?.detail || "Failed to update recipient.";
        toast.error(detail);
      })
      .finally(() => setIsSaving(false));
  };

  // ── DELETE ───────────────────────────────────────────
  const confirmRemoveRecipient = () => {
    if (recipientToDelete) {
      axios.delete(`/api/v1/email-recipients/${recipientToDelete}`).then(() => {
        fetchData();
        setRecipientToDelete(null);
        toast.success("Recipient removed successfully.");
      }).catch(() => toast.error("Failed to remove recipient."));
    }
  };

  if (isLoading) return <LoadingScreen />;

  return (
    <div className="p-8 space-y-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Email Configuration</h1>
        <p className="text-muted-foreground mt-2">Manage Email Recipients for NDC Notifications</p>
      </div>

      <div className="bg-card rounded-[4px] p-6 border border-border">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold">Email Recipients</h3>
          <button
            onClick={() => { setIsAdding(!isAdding); setNewRecipient(EMPTY_FORM); }}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-[4px] hover:bg-primary/90 transition-colors text-sm"
          >
            <Plus className="w-4 h-4" />
            Add Recipient
          </button>
        </div>

        {/* Add form */}
        {isAdding && (
          <div className="mb-6 p-4 bg-muted rounded-[4px] space-y-4 border border-border">
            <h4 className="font-semibold text-sm">Add New Recipient</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={newRecipient.name}
                  onChange={(e) => setNewRecipient({ ...newRecipient, name: e.target.value })}
                  className="w-full px-3 py-2 border border-border rounded-[4px] bg-input-background focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                  placeholder="Enter name"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Email <span className="text-red-500">*</span>
                </label>
                <input
                  type="email"
                  value={newRecipient.email}
                  onChange={(e) => setNewRecipient({ ...newRecipient, email: e.target.value })}
                  className="w-full px-3 py-2 border border-border rounded-[4px] bg-input-background focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                  placeholder="email@adani.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Department <span className="text-red-500">*</span>
                </label>
                <select
                  value={newRecipient.department}
                  onChange={(e) => setNewRecipient({ ...newRecipient, department: e.target.value })}
                  className="w-full px-3 py-2 border border-border rounded-[4px] bg-input-background focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                >
                  <option value="">Select Department</option>
                  {DEPARTMENTS.map((dept) => (
                    <option key={dept} value={dept}>{dept}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Role</label>
                <input
                  type="text"
                  value={newRecipient.role}
                  onChange={(e) => setNewRecipient({ ...newRecipient, role: e.target.value })}
                  className="w-full px-3 py-2 border border-border rounded-[4px] bg-input-background focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                  placeholder="e.g., Manager, Head"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleAddRecipient}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-[4px] hover:bg-primary/90 transition-colors text-sm"
              >
                Add Recipient
              </button>
              <button
                onClick={() => { setIsAdding(false); setNewRecipient(EMPTY_FORM); }}
                className="px-4 py-2 bg-muted text-foreground rounded-[4px] hover:bg-muted/80 transition-colors border border-border text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground tracking-wide">Name</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground tracking-wide">Email</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground tracking-wide">Department</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground tracking-wide">Role</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground tracking-wide">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-card divide-y divide-border">
              {recipients.map((recipient) => {
                const isEditing = editingId === recipient.id;
                return (
                  <tr key={recipient.id} className={`transition-colors ${isEditing ? "bg-blue-50/60 dark:bg-blue-900/10" : "hover:bg-muted/50"}`}>
                    {/* Name */}
                    <td className="px-4 py-2.5 text-sm font-medium">
                      {isEditing ? (
                        <input
                          type="text"
                          value={editDraft.name}
                          onChange={(e) => setEditDraft({ ...editDraft, name: e.target.value })}
                          className="w-full px-2 py-1 border border-border rounded-[4px] bg-background focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                        />
                      ) : recipient.name}
                    </td>
                    {/* Email */}
                    <td className="px-4 py-2.5 text-sm">
                      {isEditing ? (
                        <input
                          type="email"
                          value={editDraft.email}
                          onChange={(e) => setEditDraft({ ...editDraft, email: e.target.value })}
                          className="w-full px-2 py-1 border border-border rounded-[4px] bg-background focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                        />
                      ) : (
                        <div className="flex items-center gap-2">
                          <Mail className="w-4 h-4 text-muted-foreground" />
                          {recipient.email}
                        </div>
                      )}
                    </td>
                    {/* Department */}
                    <td className="px-4 py-2.5 text-sm">
                      {isEditing ? (
                        <select
                          value={editDraft.department}
                          onChange={(e) => setEditDraft({ ...editDraft, department: e.target.value })}
                          className="w-full px-2 py-1 border border-border rounded-[4px] bg-background focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                        >
                          <option value="">Select Department</option>
                          {DEPARTMENTS.map((dept) => (
                            <option key={dept} value={dept}>{dept}</option>
                          ))}
                        </select>
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-[4px] text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                          {recipient.department}
                        </span>
                      )}
                    </td>
                    {/* Role */}
                    <td className="px-4 py-2.5 text-sm text-muted-foreground">
                      {isEditing ? (
                        <input
                          type="text"
                          value={editDraft.role}
                          onChange={(e) => setEditDraft({ ...editDraft, role: e.target.value })}
                          className="w-full px-2 py-1 border border-border rounded-[4px] bg-background focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                          placeholder="e.g., Manager"
                        />
                      ) : (recipient.role || "—")}
                    </td>
                    {/* Actions */}
                    <td className="px-4 py-2.5 text-sm">
                      {isEditing ? (
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={saveEdit}
                            disabled={isSaving}
                            className="flex items-center gap-1 px-3 py-1.5 rounded-[4px] bg-primary text-primary-foreground hover:bg-primary/90 transition-colors text-xs font-medium disabled:opacity-50"
                            title="Save changes"
                          >
                            <Check className="w-3.5 h-3.5" />
                            {isSaving ? "Saving…" : "Save"}
                          </button>
                          <button
                            onClick={cancelEdit}
                            className="flex items-center gap-1 px-3 py-1.5 rounded-[4px] bg-muted text-foreground hover:bg-muted/80 border border-border transition-colors text-xs font-medium"
                            title="Cancel"
                          >
                            <X className="w-3.5 h-3.5" />
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => startEdit(recipient)}
                            className="p-1.5 rounded-[4px] bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors"
                            title="Edit Recipient"
                          >
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setRecipientToDelete(recipient.id)}
                            className="p-1.5 rounded-[4px] bg-red-50 text-red-600 hover:bg-red-100 transition-colors"
                            title="Remove Recipient"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
              {recipients.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground text-sm">
                    No recipients configured. Click "Add Recipient" to get started.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Delete confirmation */}
      <AlertDialog open={!!recipientToDelete} onOpenChange={(open) => !open && setRecipientToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove this recipient?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. The recipient will be permanently removed from the email configuration.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmRemoveRecipient} className="bg-red-600 text-white hover:bg-red-700">
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
