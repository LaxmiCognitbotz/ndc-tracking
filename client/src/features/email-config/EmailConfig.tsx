import { useState, useEffect } from "react";
import axios from "../../lib/axios";
import { Mail, Plus, Trash2, Save } from "lucide-react";
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



export function EmailConfig() {
  const [recipients, setRecipients] = useState<EmailRecipient[]>([]);
  const [isLoading, setIsLoading] = useState(true);

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

  const [newRecipient, setNewRecipient] = useState<Omit<EmailRecipient, "id">>({
    name: "",
    email: "",
    department: "",
    role: "",
  });
  const [isAdding, setIsAdding] = useState(false);
  const [recipientToDelete, setRecipientToDelete] = useState<string | null>(null);

  const handleAddRecipient = () => {
    if (newRecipient.name && newRecipient.email && newRecipient.department) {
      axios.post("/api/v1/email-recipients", newRecipient).then(() => {
        fetchData();
        setNewRecipient({ name: "", email: "", department: "", role: "" });
        setIsAdding(false);
        toast.success("Recipient added successfully");
      });
    }
  };

  const handleRemoveRecipient = (id: string) => {
    setRecipientToDelete(id);
  };

  const confirmRemoveRecipient = () => {
    if (recipientToDelete) {
      axios.delete(`/api/v1/email-recipients/${recipientToDelete}`).then(() => {
        fetchData();
        setRecipientToDelete(null);
        toast.success("Recipient removed successfully");
      });
    }
  };

  const handleSave = () => {
    toast.success("Email configuration saved successfully!");
    // Implementation would save to backend/database
  };

  const departments = [
    "RM",
    "IT",
    "HR",
    "Finance",
    "Telecom",
    "Security",
    "Administration",
    "Safety",
    "Operations & Maintenance",
    "GCC HR",
  ];

  if (isLoading) return <LoadingScreen />;

  return (
    <div className="p-8 space-y-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Email Configuration</h1>
        <p className="text-muted-foreground mt-2">Manage Email Recipients for NDC Notifications</p>
      </div>

      {/* Add New Recipient */}
      <div className="bg-card rounded-[4px] p-6 border border-border">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold">Email Recipients</h3>
          <button
            onClick={() => setIsAdding(!isAdding)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-[4px] hover:bg-primary/90 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Recipient
          </button>
        </div>

        {isAdding && (
          <div className="mb-6 p-4 bg-muted rounded-[4px] space-y-4">
            <h4 className="font-semibold">Add New Recipient</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={newRecipient.name}
                  onChange={(e) => setNewRecipient({ ...newRecipient, name: e.target.value })}
                  className="w-full px-3 py-2 border border-border rounded-[4px] bg-input-background focus:outline-none focus:ring-2 focus:ring-primary"
                  placeholder="Enter name"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Email <span className="text-red-500">*</span>
                </label>
                <input
                  type="email"
                  value={newRecipient.email}
                  onChange={(e) => setNewRecipient({ ...newRecipient, email: e.target.value })}
                  className="w-full px-3 py-2 border border-border rounded-[4px] bg-input-background focus:outline-none focus:ring-2 focus:ring-primary"
                  placeholder="email@adani.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Department <span className="text-red-500">*</span>
                </label>
                <select
                  value={newRecipient.department}
                  onChange={(e) => setNewRecipient({ ...newRecipient, department: e.target.value })}
                  className="w-full px-3 py-2 border border-border rounded-[4px] bg-input-background focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="">Select Department</option>
                  {departments.map((dept) => (
                    <option key={dept} value={dept}>
                      {dept}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Role</label>
                <input
                  type="text"
                  value={newRecipient.role}
                  onChange={(e) => setNewRecipient({ ...newRecipient, role: e.target.value })}
                  className="w-full px-3 py-2 border border-border rounded-[4px] bg-input-background focus:outline-none focus:ring-2 focus:ring-primary"
                  placeholder="e.g., Manager, Head"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleAddRecipient}
                className="px-4 py-2 bg-green-600 text-white rounded-[4px] hover:bg-green-700 transition-colors"
              >
                Add Recipient
              </button>
              <button
                onClick={() => {
                  setIsAdding(false);
                  setNewRecipient({ name: "", email: "", department: "", role: "" });
                }}
                className="px-4 py-2 bg-muted text-foreground rounded-[4px] hover:bg-muted/80 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Recipients Table */}
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground tracking-wide">
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground tracking-wide">
                  Email
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground tracking-wide">
                  Department
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground tracking-wide">
                  Role
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground tracking-wide">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-card divide-y divide-border">
              {recipients.map((recipient) => (
                <tr key={recipient.id} className="hover:bg-muted/50">
                  <td className="px-4 py-3 text-sm font-medium">{recipient.name}</td>
                  <td className="px-4 py-3 text-sm">
                    <div className="flex items-center gap-2">
                      <Mail className="w-4 h-4 text-muted-foreground" />
                      {recipient.email}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-[4px] text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                      {recipient.department}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {recipient.role || "-"}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <button
                      onClick={() => handleRemoveRecipient(recipient.id)}
                      className="p-1.5 rounded-[4px] bg-red-50 text-red-600 hover:bg-red-100 transition-colors"
                      title="Remove Recipient"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
              {recipients.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                    No recipients configured
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          className="flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-[4px] hover:bg-primary/90 transition-colors"
        >
          <Save className="w-5 h-5" />
          Save Configuration
        </button>
      </div>
      <AlertDialog open={!!recipientToDelete} onOpenChange={(open) => !open && setRecipientToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will permanently remove the email recipient from the configuration.
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
